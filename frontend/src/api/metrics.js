import { api } from "./client";

/** GET /api/metrics/dashboard/{empresa_id} — totais do dia, médias e picos */
export function getDashboardMetrics(empresaId) {
  return api.get(`/api/metrics/dashboard/${empresaId}`).then((r) => r.data);
}
