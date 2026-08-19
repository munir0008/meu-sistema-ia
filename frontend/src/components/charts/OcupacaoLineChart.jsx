import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "../../context/ThemeContext";

/**
 * Fluxo de ocupação (pessoas detectadas, em média) ao longo do turno — construído a
 * partir de `ocupacao_por_hora` (GET /api/metrics/dashboard/{cliente_id}), amostrado
 * periodicamente pelo backend a cada câmera (ver vision.py, OCUPACAO_AMOSTRA_SEGUNDOS).
 */
export default function OcupacaoLineChart({ ocupacaoPorHora = [] }) {
  const { isDark } = useTheme();
  const corGrade = isDark ? "#27272a" : "#e4e4e7";
  const corTick = "#71717a"; // neutral-500: legível tanto no fundo claro quanto no escuro

  const porHora = new Map(ocupacaoPorHora.map((o) => [o.hora, o.media_pessoas]));
  const dados = Array.from({ length: 24 }, (_, hora) => ({
    hora: `${String(hora).padStart(2, "0")}h`,
    pessoas: porHora.get(hora) ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={dados} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={corGrade} vertical={false} />
        <XAxis
          dataKey="hora"
          tick={{ fill: corTick, fontSize: 11 }}
          axisLine={{ stroke: corGrade }}
          tickLine={false}
          interval={2}
        />
        <YAxis tick={{ fill: corTick, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{
            background: isDark ? "#18181c" : "#ffffff",
            border: `1px solid ${corGrade}`,
            borderRadius: 8,
            fontSize: 12,
            color: isDark ? "#e4e4e7" : "#18181b",
          }}
          labelStyle={{ color: corTick }}
        />
        <Line
          type="monotone"
          dataKey="pessoas"
          name="Pessoas (média)"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
