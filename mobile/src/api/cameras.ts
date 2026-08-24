import { api, API_URL } from "./client";
import type { Camera } from "@/types/api";

/** GET /api/admin/cameras (schemas.CameraOut, sem filtro de empresa: o backend já isola por usuário). */
export async function listarCameras(): Promise<Camera[]> {
  const { data } = await api.get<Camera[]>("/api/admin/cameras");
  return data;
}

/**
 * URL do stream MJPEG (multipart/x-mixed-replace) de uma câmera, com o JWT na
 * própria query string — mesma técnica do painel web (ver
 * frontend/src/api/cameras.getVideoFeedUrl e
 * backend/auth.get_current_usuario_stream): não dá pra anexar um header
 * Authorization a uma requisição de imagem/WebView carregando uma URL direto,
 * então o backend também aceita o token via `?token=`.
 *
 * Consumida dentro de uma WebView (ver components/CameraStreamView.tsx) — o
 * <Image>/<img> nativo do React Native NÃO renderiza um stream MJPEG
 * contínuo (só entende uma imagem estática por resposta); o motor de
 * navegador embutido na WebView, sim, do mesmo jeito que um <img> de
 * navegador desktop.
 */
export function urlStreamCamera(cameraId: number, token: string): string {
  return `${API_URL}/api/video_feed/${cameraId}?token=${encodeURIComponent(token)}`;
}
