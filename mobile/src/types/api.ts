/**
 * Tipos espelhando os schemas Pydantic do backend (ver backend/schemas.py e
 * backend/models.py) — mantidos manualmente em sincronia, já que o mobile
 * consome a mesma API REST do painel web sem gerar cliente automaticamente.
 * Só os campos que o app mobile realmente usa estão tipados; campos extras
 * que a API devolve e o app ignora não quebram nada (TS estrutural).
 */

// ---------- Auth ----------
export interface LoginRequest {
  email: string;
  senha: string;
}

export type RoleUsuario = "SUPER_ADMIN" | "ADMIN" | "USER";
export type StatusAssinatura = "trial" | "pending_payment" | "active" | "past_due" | "canceled" | "unpaid";

/** Resposta de POST /api/auth/login (schemas.Token). */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: RoleUsuario;
  usuario_id: number;
  empresa_id: number | null;
  nome_empresa: string;
  status_assinatura: StatusAssinatura | null;
}

/** Sessão persistida no AsyncStorage (ver src/context/AuthContext.tsx). */
export interface SessaoUsuario {
  token: string;
  role: RoleUsuario;
  usuarioId: number;
  empresaId: number | null;
  nomeEmpresa: string;
}

// ---------- Empresa / Assinatura (GET /api/empresa/minha) ----------
export type PlanoAssinatura = "completo";

/** schemas.EmpresaOut — só os campos que a tela de Assinatura (read-only) usa. */
export interface Empresa {
  id: number;
  nome_empresa: string;
  criado_em: string;
  status_assinatura: StatusAssinatura;
  plano_atual: PlanoAssinatura | null;
  data_fim_periodo: string | null;
  total_cameras: number;
}

// ---------- Câmeras ----------
export type StatusCamera = "online" | "offline";
// "balcao_loja" é o único perfil selecionável hoje (produto simplificado
// 100% varejo) — "escritorio"/"estoque" ainda podem aparecer em câmeras
// legadas (ver backend/models.PerfilCamera), por isso o tipo aceita string.
export type PerfilCamera = "balcao_loja" | "escritorio" | "estoque";

/** Um item de GET /api/admin/cameras (schemas.CameraOut). */
export interface Camera {
  id: number;
  empresa_id: number;
  nome_camera: string;
  rtsp_url: string;
  perfil_ativo: PerfilCamera;
  status: StatusCamera;
}

// ---------- Dashboard (GET /api/metrics/dashboard/{empresa_id}) ----------
export interface HorarioPico {
  hora: number;
  total_eventos: number;
}

export interface OcupacaoPorHora {
  hora: number;
  media_pessoas: number;
}

export interface MetricasPorCamera {
  nome_camera: string;
  total_atendimentos: number;
  tempo_medio_atendimento_segundos: number;
  media_pessoas_detectadas: number;
}

/** Tópico 1 — Perda de Vendas & Gargalos (ver schemas.MetricasFila). */
export interface MetricasFila {
  tempo_medio_espera_segundos: number;
  total_clientes_na_fila: number;
  total_desistencias: number;
  taxa_desistencia_pct: number;
  picos_fila_sem_atendente: number;
}

export interface PresencaPorHora {
  hora: number;
  media_atendentes_presentes: number;
  media_clientes_presentes: number;
}

/** Tópico 2 — Eficiência da Equipe (ver schemas.MetricasEquipe). */
export interface MetricasEquipe {
  taxa_ociosidade_balcao_pct: number;
  tempo_no_posto_segundos: number;
  tempo_em_atendimento_segundos: number;
  ratio_atendimento_pct: number | null;
  distribuicao_por_hora: PresencaPorHora[];
}

export interface RankingCameraItem {
  camera_id: number;
  nome_camera: string;
  total_atendimentos_concluidos: number;
  tempo_medio_atendimento_segundos: number;
  taxa_desistencia_pct: number;
}

export interface RankingZonas {
  tabela: RankingCameraItem[];
  camera_mais_rapida_id: number | null;
  camera_maior_desistencia_id: number | null;
}

/** Resposta completa de GET /api/metrics/dashboard/{empresa_id} (schemas.DashboardMetrics). */
export interface DashboardMetrics {
  empresa_id: number;
  data_referencia: string;
  periodo: "hoje" | "7d" | "30d";
  total_atendimentos: number;
  atendimentos_concluidos: number;
  atendimentos_abandonados: number;
  tempo_medio_atendimento_segundos: number;
  pico_pessoas_detectadas: number;
  media_pessoas_detectadas: number;
  tempo_total_inatividade_segundos: number;
  horarios_pico: HorarioPico[];
  ocupacao_por_hora: OcupacaoPorHora[];
  por_camera: Record<number, MetricasPorCamera>;
  fila: MetricasFila;
  equipe: MetricasEquipe;
  ranking: RankingZonas;
}

/** Formato do corpo de erro que o backend devolve (HTTPException.detail). */
export interface ApiErrorBody {
  detail?: string | { code?: string; message?: string; [key: string]: unknown };
}
