import { api, API_URL, TOKEN_STORAGE_KEY } from "./client";

/**
 * Valor de `rtsp_url` que sinaliza "esta câmera não é RTSP/webcam-local aberta
 * pelo backend — é a webcam do PRÓPRIO NAVEGADOR de quem está vendo a página,
 * capturada e enviada via WebSocket" (ver WebcamCapturePusher.jsx e
 * backend/routes.py:camera_ingest). Precisa bater exatamente com
 * `vision.FONTE_WEBCAM_NAVEGADOR` no backend.
 */
export const FONTE_WEBCAM_NAVEGADOR = "browser";

/**
 * GET /api/admin/cameras — lista câmeras.
 * ADMIN/USER sempre recebem só as da própria empresa; SUPER_ADMIN pode passar
 * `empresaId` para filtrar por uma empresa específica (usado no painel admin)
 * ou omitir para ver todas.
 */
export function listarCameras(empresaId) {
  return api
    .get("/api/admin/cameras", { params: empresaId ? { empresa_id: empresaId } : {} })
    .then((r) => r.data);
}

/** POST /api/admin/cameras — `empresa_id` só é considerado quando quem cria é SUPER_ADMIN. */
export function criarCamera({ empresa_id, nome_camera, rtsp_url, perfil_ativo }) {
  return api
    .post("/api/admin/cameras", { empresa_id, nome_camera, rtsp_url, perfil_ativo })
    .then((r) => r.data);
}

/** PUT /api/admin/cameras/{id} */
export function atualizarCamera(id, payload) {
  return api.put(`/api/admin/cameras/${id}`, payload).then((r) => r.data);
}

/** DELETE /api/admin/cameras/{id} */
export function removerCamera(id) {
  return api.delete(`/api/admin/cameras/${id}`);
}

/** GET /api/admin/cameras/{id}/zonas */
export function listarZonas(cameraId) {
  return api.get(`/api/admin/cameras/${cameraId}/zonas`).then((r) => r.data);
}

/** POST /api/admin/cameras/{id}/zonas — substitui todas as zonas da câmera */
export function salvarZonas(cameraId, zonas) {
  return api
    .post(`/api/admin/cameras/${cameraId}/zonas`, { zonas })
    .then((r) => r.data);
}

/**
 * URL do streaming MJPEG processado (com blur/anonimização e overlay de zonas
 * já aplicados pelo backend). Uma tag <img> não envia header Authorization,
 * então o token vai via query string (?token=...) — suportado especificamente
 * nesse endpoint pelo backend.
 */
export function getVideoFeedUrl(cameraId) {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return `${API_URL}/api/video_feed/${cameraId}?token=${encodeURIComponent(token || "")}`;
}

/**
 * URL do WebSocket que recebe os frames da webcam do NAVEGADOR (câmeras com
 * `rtsp_url === FONTE_WEBCAM_NAVEGADOR`) — ver WebcamCapturePusher.jsx. Mesmo
 * esquema de auth por query string que getVideoFeedUrl (WebSocket nativo do
 * navegador também não manda header Authorization). `API_URL` troca de
 * http(s) para ws(s) automaticamente.
 */
export function getCameraIngestWsUrl(cameraId) {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}/api/camera_ingest/${cameraId}?token=${encodeURIComponent(token || "")}`;
}
