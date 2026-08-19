import { BarChart3, Clock, Users, Video as VideoIcon } from "lucide-react";
import { useEffect, useState } from "react";
import * as camerasApi from "../../api/cameras";
import * as metricsApi from "../../api/metrics";
import { formatDuracaoLonga, nivelMovimentacao } from "../../utils/format";
import CameraCard from "../cameras/CameraCard";
import FluxoPorHoraChart from "../charts/FluxoPorHoraChart";
import OcupacaoLineChart from "../charts/OcupacaoLineChart";
import Card from "../ui/Card";
import ErrorBanner from "../ui/ErrorBanner";
import KpiCard from "../ui/KpiCard";
import Spinner from "../ui/Spinner";

/**
 * Painel de BI de uma empresa: transmissão ao vivo + KPIs do dia + gráficos.
 * Reutilizado tanto pela própria empresa (ADMIN/USER, `/dashboard`) quanto pelo
 * SUPER_ADMIN (aba "Dashboard" de qualquer empresa dentro do painel admin) — por
 * isso recebe `empresaId` como prop em vez de ler do usuário logado.
 */
export default function EmpresaBiPanel({ empresaId }) {
  const [metricas, setMetricas] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    if (!empresaId) return;
    let ativo = true;

    async function carregar() {
      setCarregando(true);
      setErro(null);
      try {
        const [dadosMetricas, dadosCameras] = await Promise.all([
          metricsApi.getDashboardMetrics(empresaId),
          camerasApi.listarCameras(empresaId),
        ]);
        if (!ativo) return;
        setMetricas(dadosMetricas);
        setCameras(dadosCameras);
      } catch (err) {
        if (!ativo) return;
        setErro(err?.response?.data?.detail || "Não foi possível carregar o dashboard.");
      } finally {
        if (ativo) setCarregando(false);
      }
    }

    carregar();
    const intervalo = setInterval(carregar, 30_000); // refresca a cada 30s
    return () => {
      ativo = false;
      clearInterval(intervalo);
    };
  }, [empresaId]);

  if (carregando && !metricas) return <Spinner label="Carregando dashboard…" />;
  if (erro && !metricas) return <ErrorBanner>{erro}</ErrorBanner>;
  if (!metricas) return null;

  const movimentacao = nivelMovimentacao(metricas.media_pessoas_detectadas);

  return (
    <div className="flex flex-col gap-6">
      <ErrorBanner>{erro}</ErrorBanner>

      <Card
        title="Transmissão ao Vivo"
        subtitle="Rostos e pessoas borrados automaticamente pelo backend (LGPD) — zonas e caixas já vêm desenhadas no vídeo"
      >
        {cameras.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center text-neutral-500">
            <VideoIcon className="size-6" />
            <p className="text-sm">Nenhuma câmera cadastrada ainda.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {cameras.map((camera) => (
              <CameraCard key={camera.id} camera={camera} />
            ))}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          icon={Users}
          label="Clientes Atendidos Hoje"
          value={metricas.atendimentos_concluidos}
          hint={`${metricas.atendimentos_abandonados} não concluídos`}
          tone="emerald"
        />
        <KpiCard
          icon={Clock}
          label="Tempo Médio por Atendimento"
          value={formatDuracaoLonga(metricas.tempo_medio_atendimento_segundos)}
          hint={`${metricas.total_atendimentos} atendimentos hoje`}
          tone="cyan"
        />
        <KpiCard
          icon={BarChart3}
          label="Ocupação / Movimentação"
          value={movimentacao.label}
          hint={`Média de ${metricas.media_pessoas_detectadas.toFixed(1)} pessoas · pico de ${metricas.pico_pessoas_detectadas}`}
          tone={movimentacao.tone}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Atendimentos por Hora" subtitle="Mapeando os horários de pico do dia">
          <FluxoPorHoraChart horariosPico={metricas.horarios_pico} />
        </Card>
        <Card title="Fluxo de Ocupação" subtitle="Pessoas detectadas (média) ao longo do turno">
          <OcupacaoLineChart ocupacaoPorHora={metricas.ocupacao_por_hora} />
        </Card>
      </div>
    </div>
  );
}
