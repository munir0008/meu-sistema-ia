import { api } from "./client";

/**
 * GET /api/metrics/dashboard/{empresa_id} — totais, médias, picos e os blocos
 * de analytics avançados (fila, equipe, ranking por câmera — Dashboard
 * Analytics Tópicos 1/2/4). `periodo`: "hoje" (padrão) | "7d" | "30d".
 */
export function getDashboardMetrics(empresaId, periodo = "hoje") {
  return api.get(`/api/metrics/dashboard/${empresaId}`, { params: { periodo } }).then((r) => r.data);
}
