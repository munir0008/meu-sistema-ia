import { Crown, TrendingDown } from "lucide-react";
import Badge from "../ui/Badge";
import { formatPercent, formatSegundosParaMinutos } from "../../utils/format";

/**
 * Dashboard Analytics Tópico 4 (Ranking e Comparativo por Câmera/Zona) — tabela
 * comparativa de performance por câmera, com destaque para a mais rápida (menor
 * espera) e a de maior perda de clientes (maior taxa de desistência).
 *
 * A granularidade é por câmera, não por zona individual: o backend não grava a
 * qual zona uma sessão de fila pertence — cada câmera de perfil balcão tem uma
 * 'Zona Cliente' e uma 'Zona Atendente' próprias, então câmera já equivale a um
 * ponto de atendimento (ver backend/routes._calcular_ranking_cameras).
 */
export default function RankingCamerasTable({ ranking }) {
  const tabela = ranking?.tabela || [];
  const idMaisRapida = ranking?.camera_mais_rapida_id ?? null;
  const idMaiorDesistencia = ranking?.camera_maior_desistencia_id ?? null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500 dark:border-neutral-800">
            <th className="py-2 pr-4 font-medium">Câmera / Zona</th>
            <th className="py-2 pr-4 font-medium">Atendimentos Concluídos</th>
            <th className="py-2 pr-4 font-medium">TMA</th>
            <th className="py-2 pr-4 font-medium">Espera Média</th>
            <th className="py-2 pr-4 font-medium">Desistência</th>
            <th className="py-2 pr-4 font-medium">Ociosidade</th>
          </tr>
        </thead>
        <tbody>
          {tabela.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-neutral-500">
                Sem dados suficientes ainda.
              </td>
            </tr>
          )}
          {tabela.map((cam) => (
            <tr key={cam.camera_id} className="border-b border-neutral-100 dark:border-neutral-900">
              <td className="py-2.5 pr-4 text-neutral-700 dark:text-neutral-200">
                <div className="flex flex-wrap items-center gap-2">
                  <span>{cam.nome_camera}</span>
                  {cam.camera_id === idMaisRapida && (
                    <Badge tone="green">
                      <Crown className="size-3" /> Mais rápida
                    </Badge>
                  )}
                  {cam.camera_id === idMaiorDesistencia && (
                    <Badge tone="red">
                      <TrendingDown className="size-3" /> Maior perda
                    </Badge>
                  )}
                </div>
              </td>
              <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                {cam.total_atendimentos_concluidos}
              </td>
              <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                {formatSegundosParaMinutos(cam.tempo_medio_atendimento_segundos)}
              </td>
              <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                {cam.tempo_medio_espera_segundos != null
                  ? formatSegundosParaMinutos(cam.tempo_medio_espera_segundos)
                  : "—"}
              </td>
              <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                {formatPercent(cam.taxa_desistencia_pct, 1)}
              </td>
              <td className="py-2.5 pr-4 text-neutral-500 dark:text-neutral-400">
                {cam.taxa_ociosidade_pct != null ? formatPercent(cam.taxa_ociosidade_pct, 1) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
