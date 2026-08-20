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
    escritorio = "escritorio"
    estoque = "estoque"


class StatusCamera(str, enum.Enum):
    online = "online"
    offline = "offline"


class TipoZona(str, enum.Enum):
    atendente = "atendente"
    cliente = "cliente"
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
    __tablename__ = "metricas_atendimento"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    duracao_segundos = Column(Float, nullable=False)
    concluido = Column(Boolean, default=False, nullable=False)


class MetricaOcupacao(Base):
    __tablename__ = "metricas_ocupacao"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    pessoas_detectadas = Column(Integer, default=0, nullable=False)
    tempo_inatividade_segundos = Column(Float, default=0.0, nullable=False)
