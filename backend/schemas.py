"""
Schemas Pydantic — contratos de entrada/saída da API.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models import PerfilCamera, PlanoAssinatura, RoleUsuario, StatusAssinatura, StatusCamera, TipoZona

Ponto = Tuple[float, float]


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class SignupRequest(BaseModel):
    """Autocadastro público: cria a Empresa (status `pending_payment`) e seu primeiro usuário (ADMIN)."""

    nome_empresa: str = Field(min_length=2)
    nome_admin: str = Field(min_length=2)
    email: EmailStr
    senha: str = Field(min_length=6)


class SignupResponse(BaseModel):
    """
    Resposta do autocadastro — de propósito SEM `access_token`: a conta nasce
    com status `pending_payment` e o frontend não faz login automático, só
    redireciona para `checkout_url` (Stripe Checkout). O admin só ganha uma
    sessão de fato fazendo login normalmente em POST /api/auth/login, depois
    de pagar (ou para retomar o checkout em /assinatura, se fechar a aba antes
    de concluir o pagamento).
    """

    empresa_id: int
    checkout_url: str


class Token(BaseModel):
    """
    Resposta do login (POST /api/auth/login). Além do JWT (que já carrega
    `role`/`usuario_id`/`empresa_id` como claims para o backend validar em
    cada request), devolvemos
    esses mesmos dados "abertos" para o frontend decidir o redirecionamento
    pós-login sem precisar decodificar o token.
    """

    access_token: str
    token_type: str = "bearer"
    role: RoleUsuario
    usuario_id: int
    empresa_id: Optional[int] = None
    nome_empresa: str = ""
    status_assinatura: Optional[StatusAssinatura] = None


# ---------- Empresa (tenant) ----------
class EmpresaBase(BaseModel):
    nome_empresa: str


class EmpresaUpdate(BaseModel):
    nome_empresa: Optional[str] = None
    status_assinatura: Optional[StatusAssinatura] = None


class EmpresaOut(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
    status_assinatura: StatusAssinatura
    plano_atual: Optional[PlanoAssinatura] = None
    data_fim_periodo: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    total_cameras: int = 0


# ---------- Usuario (login/RBAC) ----------
class UsuarioBase(BaseModel):
    nome: Optional[str] = None
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    """Usado pelo SUPER_ADMIN para criar outras contas SUPER_ADMIN (sem empresa)."""

    senha: str = Field(min_length=6)


class EquipeUsuarioCreate(UsuarioBase):
    """Usado por um ADMIN para criar contas USER dentro da própria empresa."""

    senha: str = Field(min_length=6)


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    senha: Optional[str] = Field(default=None, min_length=6)


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: RoleUsuario
    empresa_id: Optional[int] = None
    criado_em: datetime


# ---------- Camera ----------
class CameraBase(BaseModel):
    nome_camera: str
    rtsp_url: str
    perfil_ativo: PerfilCamera = PerfilCamera.balcao_loja


class CameraCreate(CameraBase):
    # Ignorado quando quem cria não é SUPER_ADMIN — nesse caso o backend força
    # a própria empresa do usuário autenticado (ver routes.criar_camera).
    empresa_id: Optional[int] = None


class CameraUpdate(BaseModel):
    nome_camera: Optional[str] = None
    rtsp_url: Optional[str] = None
    perfil_ativo: Optional[PerfilCamera] = None
    status: Optional[StatusCamera] = None


class CameraOut(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    status: StatusCamera


# ---------- Zona ----------
class ZonaCreate(BaseModel):
    tipo_zona: TipoZona
    coordenadas: List[Ponto] = Field(
        description="Pontos [x, y] normalizados (0.0 a 1.0) formando o polígono/retângulo da zona"
    )


class ZonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    tipo_zona: TipoZona
    coordenadas: List[Ponto]


class ZonasBulkCreate(BaseModel):
    """Payload para salvar (substituindo as existentes) todas as zonas desenhadas de uma câmera."""

    zonas: List[ZonaCreate]


# ---------- Pagamentos (Stripe) ----------
class CheckoutSessionRequest(BaseModel):
    plano: PlanoAssinatura


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class CustomerPortalOut(BaseModel):
    portal_url: str


# ---------- Métricas / Dashboard ----------
class HorarioPico(BaseModel):
    hora: int
    total_eventos: int


class OcupacaoPorHora(BaseModel):
    hora: int
    media_pessoas: float


class MetricasPorCamera(BaseModel):
    nome_camera: str
    total_atendimentos: int
    tempo_medio_atendimento_segundos: float
    media_pessoas_detectadas: float


class DashboardMetrics(BaseModel):
    empresa_id: int
    data_referencia: str
    total_atendimentos: int
    atendimentos_concluidos: int
    atendimentos_abandonados: int
    tempo_medio_atendimento_segundos: float
    pico_pessoas_detectadas: int
    media_pessoas_detectadas: float
    tempo_total_inatividade_segundos: float
    horarios_pico: List[HorarioPico]
    ocupacao_por_hora: List[OcupacaoPorHora]
    por_camera: Dict[int, MetricasPorCamera]
