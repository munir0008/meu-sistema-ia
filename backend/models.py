"""
Modelos ORM (SQLAlchemy) — refletem as tabelas do banco multi-tenant.

Separação Empresa (tenant/cobrança) x Usuario (login/RBAC):
- `Empresa`: a organização cliente do SaaS — dona das câmeras e da assinatura
  Stripe. Não faz login.
- `Usuario`: uma conta de acesso, vinculada a uma `Empresa` (exceto
  SUPER_ADMIN, que é global e não pertence a nenhuma empresa).
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class PerfilCamera(str, enum.Enum):
    balcao_loja = "balcao_loja"
    # Legado: produto simplificado 100% para varejo/supermercado — não é mais
    # possível criar/migrar uma câmera para estes perfis (ver
    # schemas.CameraCreate/CameraUpdate, que restringem a só "balcao_loja").
    # Mantidos aqui (em vez de removidos) só para não quebrar a leitura de
    # câmeras antigas que já tinham um desses perfis configurado — o ENUM
    # nativo do Postgres também não permite remover um label depois de criado
    # sem recriar o tipo. `vision.VideoProcessor` ainda sabe processá-los
    # (_atualizar_escritorio/_atualizar_estoque) caso alguma câmera legada
    # ainda os use.
    escritorio = "escritorio"
    estoque = "estoque"


class StatusCamera(str, enum.Enum):
    online = "online"
    offline = "offline"


class TipoZona(str, enum.Enum):
    atendente = "atendente"
    cliente = "cliente"
    # Legado: zonas dos perfis escritorio/estoque (hoje legados — ver
    # PerfilCamera acima). Não é mais possível DESENHAR zona nova destes
    # tipos (ver schemas.ZonaCreate, restrita a atendente/cliente); mantidos
    # aqui só para não quebrar a leitura de zonas antigas já desenhadas.
    trabalho = "trabalho"
    neutra = "neutra"


class RoleUsuario(str, enum.Enum):
    """
    Papel de acesso (RBAC) de cada conta em `usuarios`:
    - SUPER_ADMIN: acesso total — gerencia todas as empresas, câmeras, zonas
      e assinaturas. Conta global (`empresa_id` nulo).
    - ADMIN: dono/gestor da empresa — CRUD completo de câmeras/zonas da
      própria empresa, gerencia a equipe (usuários USER) e a assinatura.
    - USER: colaborador da empresa — mesmo CRUD de câmeras/zonas que ADMIN,
      mas não gerencia equipe nem assinatura.
    """

    super_admin = "SUPER_ADMIN"
    admin = "ADMIN"
    user = "USER"


class StatusAssinatura(str, enum.Enum):
    # Legado: cadastros feitos antes do pagamento se tornar obrigatório no
    # autocadastro (ver routes.signup). NÃO concede mais acesso — excluído de
    # auth._ASSINATURAS_VALIDAS — mantido só para não quebrar a leitura de
    # linhas antigas no banco (o tipo ENUM nativo do Postgres não permite
    # remover um label depois de criado).
    trial = "trial"
    # Estado inicial de toda empresa recém-cadastrada: existe no banco, mas
    # nenhuma rota de negócio libera acesso até o webhook da Stripe confirmar
    # o pagamento (checkout.session.completed) e promover para `active`.
    pending_payment = "pending_payment"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"


class PlanoAssinatura(str, enum.Enum):
    """Plano único da plataforma — ver STRIPE_PRICE_ID_UNICO em config.py."""

    completo = "completo"


class TipoEventoZona(str, enum.Enum):
    """
    Vocabulário de telemetria do pipeline de visão computacional (perfil
    balcao_loja) — ver vision.VideoProcessor._atualizar_atendimento_balcao e
    models.EventoZona. Cada valor é um evento discreto e já debounced (não
    dispara em flicker de detecção — ver config.ZONA_DEBOUNCE_SEGUNDOS).
    """

    client_entered_zone = "CLIENT_ENTERED_ZONE"
    client_exited_zone = "CLIENT_EXITED_ZONE"
    attendant_entered_zone = "ATTENDANT_ENTERED_ZONE"
    attendant_exited_zone = "ATTENDANT_EXITED_ZONE"
    # Presença conjunta (atendente + este cliente) sustentada por
    # >= ATENDIMENTO_MIN_SEGUNDOS — mesmo instante em que MetricaAtendimento.concluido
    # passaria a True para essa sessão.
    service_started = "SERVICE_STARTED"
    # Cliente saiu da zona depois de um SERVICE_STARTED — duracao_segundos é o
    # tempo efetivo em atendimento (do SERVICE_STARTED até a saída).
    service_ended = "SERVICE_ENDED"
    # Cliente saiu da zona sem nunca ter havido SERVICE_STARTED, tendo permanecido
    # >= DESISTENCIA_MIN_SEGUNDOS — equivalente a MetricaAtendimento.desistiu=True.
    abandonment_detected = "ABANDONMENT_DETECTED"


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nome_empresa = Column(String(150), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Billing (Stripe) ---
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    status_assinatura = Column(
        SAEnum(StatusAssinatura), default=StatusAssinatura.trial, nullable=False
    )
    plano_atual = Column(SAEnum(PlanoAssinatura), nullable=True)
    data_fim_periodo = Column(DateTime, nullable=True)

    usuarios = relationship("Usuario", back_populates="empresa", cascade="all, delete-orphan")
    cameras = relationship("Camera", back_populates="empresa", cascade="all, delete-orphan")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    # Nulo somente para SUPER_ADMIN (conta global, não pertence a nenhuma empresa).
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    nome = Column(String(150), nullable=True)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleUsuario), default=RoleUsuario.user, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    empresa = relationship("Empresa", back_populates="usuarios")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nome_camera = Column(String(150), nullable=False)
    # Para testes locais use "0" (índice da webcam). Em produção, a URL RTSP/ONVIF da câmera.
    rtsp_url = Column(String(500), nullable=False)
    perfil_ativo = Column(SAEnum(PerfilCamera), default=PerfilCamera.balcao_loja, nullable=False)
    status = Column(SAEnum(StatusCamera), default=StatusCamera.offline, nullable=False)

    empresa = relationship("Empresa", back_populates="cameras")
    zonas = relationship("Zona", back_populates="camera", cascade="all, delete-orphan")


class Zona(Base):
    __tablename__ = "zonas"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    tipo_zona = Column(SAEnum(TipoZona), nullable=False)
    # JSON com lista de pontos normalizados (0.0-1.0) do polígono: [[x1,y1],[x2,y2],...]
    coordenadas_json = Column(Text, nullable=False)

    camera = relationship("Camera", back_populates="zonas")


class MetricaAtendimento(Base):
    """
    Uma linha por "sessão de fila": da entrada de uma pessoa na zona 'Cliente' até
    sua saída dessa zona — independente de ter chegado a ser atendida ou não (ver
    vision.VideoProcessor._atualizar_atendimento_balcao). Base do Dashboard
    Analytics Tópico 1 (Perda de Vendas & Gargalos de Atendimento).
    """

    __tablename__ = "metricas_atendimento"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    # Tempo total da sessão na zona 'Cliente' (da entrada à saída) — antes desta
    # métrica existir, era só a duração da presença conjunta com o atendente;
    # agora cobre também clientes que nunca chegaram a ser atendidos.
    duracao_segundos = Column(Float, nullable=False)
    # True quando a presença conjunta atendente+cliente foi sustentada por
    # >= ATENDIMENTO_MIN_SEGUNDOS (ver config.py) — "Atendimento Em Andamento".
    concluido = Column(Boolean, default=False, nullable=False)
    # Segundos entre a entrada na zona 'Cliente' e a primeira vez que um atendente
    # foi detectado presente na zona 'Atendente' durante essa sessão. Nulo quando
    # nenhum atendente esteve presente enquanto o cliente estava na zona.
    tempo_espera_segundos = Column(Float, nullable=True)
    # True quando o cliente permaneceu >= DESISTENCIA_MIN_SEGUNDOS na zona sem
    # nunca ter havido um atendente presente (tempo_espera_segundos nulo).
    desistiu = Column(Boolean, default=False, nullable=False)


class MetricaOcupacao(Base):
    __tablename__ = "metricas_ocupacao"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    pessoas_detectadas = Column(Integer, default=0, nullable=False)
    tempo_inatividade_segundos = Column(Float, default=0.0, nullable=False)


class AmostraBalcao(Base):
    """
    Amostragem periódica (a cada OCUPACAO_AMOSTRA_SEGUNDOS, ver config.py) da
    ocupação das zonas 'Atendente'/'Trabalho' e 'Cliente' de câmeras com perfil
    balcao_loja — ver vision.VideoProcessor._atualizar_amostra_balcao.

    Base do Dashboard Analytics Tópico 2 (Eficiência e Desempenho da Equipe):
    ociosidade do balcão, tempo no posto vs. tempo em atendimento, e distribuição
    de presença por horário — tudo derivado por amostragem (não há um relógio
    contínuo por atendente), o mesmo padrão já usado por MetricaOcupacao.
    """

    __tablename__ = "amostras_balcao"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    atendentes_presentes = Column(Integer, default=0, nullable=False)
    clientes_presentes = Column(Integer, default=0, nullable=False)


class EventoZona(Base):
    """
    Log granular de telemetria do pipeline de visão (perfil balcao_loja): uma
    linha por evento de zona/atendimento (ver TipoEventoZona), sempre disparado
    a partir de uma TRANSIÇÃO de estado já debounced — nunca frame a frame (ver
    vision.VideoProcessor._atualizar_debounce e config.ZONA_DEBOUNCE_SEGUNDOS).

    Complementa (não substitui) `MetricaAtendimento`: esta tabela é o registro
    granular evento-a-evento (útil para auditoria/depuração e uma futura feed de
    atividade em tempo real); `MetricaAtendimento` continua sendo o agregado por
    sessão que o Dashboard Analytics consome hoje.
    """

    __tablename__ = "eventos_zona"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    tipo_evento = Column(SAEnum(TipoEventoZona), nullable=False, index=True)
    # ID de rastreamento (ByteTrack) da pessoa envolvida no evento.
    track_id = Column(Integer, nullable=True)
    # Duração associada ao evento, quando fizer sentido (nulo em eventos de
    # entrada, que ainda não têm duração a medir):
    #   CLIENT_EXITED_ZONE / ATTENDANT_EXITED_ZONE -> tempo total na zona
    #   SERVICE_ENDED -> tempo efetivo em atendimento (desde o SERVICE_STARTED)
    #   ABANDONMENT_DETECTED -> tempo total esperado na fila
    duracao_segundos = Column(Float, nullable=True)


class AlertaFila(Base):
    """
    Um evento por "pico de fila sem atendente": a zona 'Cliente' atingiu
    PICO_FILA_MIN_PESSOAS (ou mais) pessoas simultâneas enquanto a zona
    'Atendente' esteve vazia por PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS contínuos
    (ver config.py e vision.VideoProcessor._atualizar_atendimento_balcao). Só um
    registro por ocorrência contínua — não repete enquanto a condição persiste.
    """

    __tablename__ = "alertas_fila"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    pessoas_na_fila = Column(Integer, nullable=False)
