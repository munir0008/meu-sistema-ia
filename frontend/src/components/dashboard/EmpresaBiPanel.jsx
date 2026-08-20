import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock,
  Percent,
  Timer,
  Trophy,
  UserX,
  Users,
  Video as VideoIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import * as camerasApi from "../../api/cameras";
import * as metricsApi from "../../api/metrics";
import { formatDuracaoLonga, formatPercent, nivelMovimentacao, PERIODO_LABELS } from "../../utils/format";
import CameraCard from "../cameras/CameraCard";
import FluxoPorHoraChart from "../charts/FluxoPorHoraChart";
import OcupacaoLineChart from "../charts/OcupacaoLineChart";
import PresencaPorHoraChart from "../charts/PresencaPorHoraChart";
import Card from "../ui/Card";
import ErrorBanner from "../ui/ErrorBanner";
import KpiCard from "../ui/KpiCard";
import PeriodoToggle from "../ui/PeriodoToggle";
import Spinner from "../ui/Spinner";
import RankingCamerasTable from "./RankingCamerasTable";

/**
 * Painel de BI de uma empresa: transmissão ao vivo + KPIs + gráficos + Dashboard
 * Analytics avançado (perda de vendas, eficiência da equipe e ranking por câmera).
 * Reutilizado tanto pela própria empresa (ADMIN/USER, `/dashboard`) quanto pelo
 * SUPER_ADMIN (aba "Dashboard" de qualquer empresa dentro do painel admin) — por
 * isso recebe `empresaId` como prop em vez de ler do usuário logado.
 */
export default function EmpresaBiPanel({ empresaId }) {
  const [periodo, setPeriodo] = useState("hoje");
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
          metricsApi.getDashboardMetrics(empresaId, periodo),
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
  }, [empresaId, periodo]);

  if (carregando && !metricas) return <Spinner label="Carregando dashboard…" />;
  if (erro && !metricas) return <ErrorBanner>{erro}</ErrorBanner>;
  if (!metricas) return null;

  const movimentacao = nivelMovimentacao(metricas.media_pessoas_detectadas);
  const rotuloPeriodo = PERIODO_LABELS[metricas.periodo] ?? PERIODO_LABELS.hoje;
  const fila = metricas.fila;
  const equipe = metricas.equipe;

  return (
    <div className="flex flex-col gap-6">
      <ErrorBanner>{erro}</ErrorBanner>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Dashboard Analytics</h2>
          <p className="text-xs text-neutral-500">Métricas calculadas {rotuloPeriodo}</p>
        </div>
        <PeriodoToggle valor={periodo} onChange={setPeriodo} />
      </div>

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
          label="Clientes Atendidos"
          value={metricas.atendimentos_concluidos}
          hint={`${metricas.atendimentos_abandonados} não concluídos · ${rotuloPeriodo}`}
          tone="emerald"
        />
        <KpiCard
          icon={Clock}
          label="Tempo Médio por Atendimento"
          value={formatDuracaoLonga(metricas.tempo_medio_atendimento_segundos)}
          hint={`${metricas.total_atendimentos} sessões de fila · ${rotuloPeriodo}`}
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

      {/* Tópico 1 — Perda de Vendas & Gargalos de Atendimento */}
      <Card
        title="Perda de Vendas & Gargalos de Atendimento"
        subtitle="Onde clientes esperam demais ou desistem antes de ser atendidos"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            icon={Timer}
            label="Tempo Médio de Espera na Fila"
            value={formatDuracaoLonga(fila.tempo_medio_espera_segundos)}
            hint={`Entrada na fila até o 1º atendente · ${rotuloPeriodo}`}
            tone="cyan"
            tooltip="Tempo médio entre o cliente entrar na zona 'Cliente' e um atendente ser detectado na zona 'Atendente' para iniciar o atendimento."
          />
          <KpiCard
            icon={UserX}
            label="Clientes Não Atendidos"
            value={fila.total_desistencias}
            hint={`de ${fila.total_clientes_na_fila} que entraram na fila`}
            tone="amber"
            tooltip="Clientes que ficaram na fila além do tempo limite configurado (padrão 180s) e saíram sem que nenhum atendente estivesse presente durante a espera."
          />
          <KpiCard
            icon={Percent}
            label="Taxa de Desistência"
            value={formatPercent(fila.taxa_desistencia_pct, 1)}
            hint="Desistências ÷ total de clientes na fila"
            tone={fila.taxa_desistencia_pct >= 20 ? "red" : "amber"}
            tooltip="(Total de desistências ÷ total de clientes que entraram na fila) × 100."
          />
          <KpiCard
            icon={AlertTriangle}
            label="Picos de Fila Sem Atendente"
            value={fila.picos_fila_sem_atendente}
            hint="2+ clientes com balcão vazio por 2+ min"
            tone={fila.picos_fila_sem_atendente > 0 ? "red" : "emerald"}
            tooltip="Quantas vezes a zona 'Cliente' teve 2 ou mais pessoas simultâneas enquanto a zona 'Atendente' ficou vazia por mais de 2 minutos seguidos."
          />
        </div>
      </Card>

      {/* Tópico 2 — Eficiência e Desempenho da Equipe */}
      <Card
        title="Eficiência e Desempenho da Equipe"
        subtitle="Quanto do tempo no posto é, de fato, tempo produtivo com cliente"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            icon={Percent}
            label="Taxa de Ociosidade do Balcão"
            value={formatPercent(equipe.taxa_ociosidade_balcao_pct, 1)}
            hint="% do horário monitorado sem nenhum atendente"
            tone={equipe.taxa_ociosidade_balcao_pct >= 50 ? "red" : "amber"}
            tooltip="Porcentagem do período monitorado em que a zona 'Atendente' (ou 'Trabalho') foi amostrada com zero pessoas detectadas."
          />
          <KpiCard
            icon={Activity}
            label="Tempo no Posto"
            value={formatDuracaoLonga(equipe.tempo_no_posto_segundos)}
            hint="Tempo total com atendente presente"
            tone="indigo"
            tooltip="Tempo total em que algum atendente foi detectado nas zonas 'Atendente' ou 'Trabalho', estimado por amostragem periódica."
          />
          <KpiCard
            icon={Clock}
            label="Tempo em Atendimento"
            value={formatDuracaoLonga(equipe.tempo_em_atendimento_segundos)}
            hint="Atendente + cliente simultâneos"
            tone="cyan"
            tooltip="Tempo em que havia, ao mesmo tempo, atendente na zona dele e cliente na zona de atendimento."
          />
          <KpiCard
            icon={Percent}
            label="Ratio Atendimento / Posto"
            value={equipe.ratio_atendimento_pct != null ? formatPercent(equipe.ratio_atendimento_pct, 1) : "—"}
            hint="Tempo produtivo ÷ tempo total no posto"
            tone="emerald"
            tooltip="Proporção do tempo no posto que foi, de fato, tempo em atendimento com cliente presente — quanto maior, mais produtivo o tempo da equipe no balcão."
          />
        </div>
        <div className="mt-5">
          <p className="mb-2 text-xs font-medium text-neutral-500">
            Presença por horário — atendentes x clientes
          </p>
          <PresencaPorHoraChart distribuicaoPorHora={equipe.distribuicao_por_hora} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Atendimentos por Hora" subtitle="Mapeando os horários de pico">
          <FluxoPorHoraChart horariosPico={metricas.horarios_pico} />
        </Card>
        <Card title="Fluxo de Ocupação" subtitle="Pessoas detectadas (média) ao longo do turno">
          <OcupacaoLineChart ocupacaoPorHora={metricas.ocupacao_por_hora} />
        </Card>
      </div>

      {/* Tópico 4 — Ranking e Comparativo por Câmera / Zona */}
      <Card
        title="Ranking e Comparativo por Câmera / Zona"
        subtitle="Onde o atendimento é mais rápido e onde a loja mais perde clientes"
        action={<Trophy className="size-4 text-amber-500" />}
      >
        <RankingCamerasTable ranking={metricas.ranking} />
      </Card>
    </div>
  );
}
