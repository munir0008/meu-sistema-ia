import { api } from "./client";
import type { DashboardMetrics } from "@/types/api";

export type PeriodoDashboard = "hoje" | "7d" | "30d";

/** GET /api/metrics/dashboard/{empresa_id} (schemas.DashboardMetrics). */
export async function buscarDashboard(
  empresaId: number,
  periodo: PeriodoDashboard = "hoje"
): Promise<DashboardMetrics> {
  const { data } = await api.get<DashboardMetrics>(`/api/metrics/dashboard/${empresaId}`, {
    params: { periodo },
  });
  return data;
}
