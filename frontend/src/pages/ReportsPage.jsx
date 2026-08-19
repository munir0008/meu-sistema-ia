import { useEffect, useState } from "react";
import * as metricsApi from "../api/metrics";
import FluxoPorHoraChart from "../components/charts/FluxoPorHoraChart";
import CentralRelatorios from "../components/reports/CentralRelatorios";
import Card from "../components/ui/Card";
import ErrorBanner from "../components/ui/ErrorBanner";
import Spinner from "../components/ui/Spinner";
import { useAuth } from "../context/AuthContext";
import { formatSegundosParaMinutos } from "../utils/format";

export default function ReportsPage() {
  const { user } = useAuth();
  const [metricas, setMetricas] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    if (!user?.empresaId) return;
    metricsApi
      .getDashboardMetrics(user.empresaId)
      .then(setMetricas)
      .catch((err) => setErro(err?.response?.data?.detail || "Não foi possível carregar o relatório."))
      .finally(() => setCarregando(false));
  }, [user?.empresaId]);

  if (carregando) return <Spinner label="Carregando relatório…" />;
  if (erro) return <ErrorBanner>{erro}</ErrorBanner>;
  if (!metricas) return null;

  const porCamera = Object.entries(metricas.por_camera);

  return (
    <div className="flex flex-col gap-6">
      <CentralRelatorios empresaId={user.empresaId} />

      <div className="flex flex-col gap-1">
        <p className="text-sm text-neutral-500">
          Visão rápida de <span className="text-neutral-700 dark:text-neutral-300">{metricas.data_referencia}</span>{" "}
          (hoje). Para outros
          períodos, use a Central de Relatórios acima para exportar em PDF ou Excel.
        </p>
      </div>

      <Card title="Horários de Pico" subtitle="Eventos de atendimento por hora do dia">
        <FluxoPorHoraChart horariosPico={metricas.horarios_pico} />
      </Card>

      <Card title="Desempenho por Câmera">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead>
              <tr className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500 dark:border-neutral-800">
                <th className="py-2 pr-4 font-medium">Câmera</th>
                <th className="py-2 pr-4 font-medium">Atendimentos</th>
                <th className="py-2 pr-4 font-medium">Tempo Médio</th>
                <th className="py-2 pr-4 font-medium">Pessoas (média)</th>
              </tr>
            </thead>
            <tbody>
              {porCamera.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-neutral-600">
                    Sem dados suficientes ainda.
                  </td>
                </tr>
              )}
              {porCamera.map(([id, cam]) => (
                <tr key={id} className="border-b border-neutral-100 dark:border-neutral-900">
                  <td className="py-2.5 pr-4 text-neutral-700 dark:text-neutral-200">{cam.nome_camera}</td>
                  <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">{cam.total_atendimentos}</td>
                  <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                    {formatSegundosParaMinutos(cam.tempo_medio_atendimento_segundos)}
                  </td>
                  <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                    {cam.media_pessoas_detectadas.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card title="Ocupação">
          <p className="text-xs text-neutral-500">Tempo total de inatividade hoje</p>
          <p className="mt-1 text-xl font-semibold text-neutral-900 dark:text-neutral-100">
            {formatSegundosParaMinutos(metricas.tempo_total_inatividade_segundos)}
          </p>
        </Card>
        <Card title="Pico de Pessoas">
          <p className="text-xs text-neutral-500">Maior contagem simultânea</p>
          <p className="mt-1 text-xl font-semibold text-neutral-900 dark:text-neutral-100">{metricas.pico_pessoas_detectadas}</p>
        </Card>
        <Card title="Abandono">
          <p className="text-xs text-neutral-500">Atendimentos não concluídos</p>
          <p className="mt-1 text-xl font-semibold text-neutral-900 dark:text-neutral-100">{metricas.atendimentos_abandonados}</p>
        </Card>
      </div>
    </div>
  );
}
