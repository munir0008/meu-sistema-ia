import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "../../context/ThemeContext";

/**
 * Fluxo de atendimentos por hora do dia. Construído a partir de `horarios_pico`
 * (GET /api/metrics/dashboard/{cliente_id}) — contagem de eventos de atendimento
 * por hora, a métrica mais próxima de "fluxo de pessoas" que o backend expõe hoje.
 */
export default function FluxoPorHoraChart({ horariosPico = [] }) {
  const { isDark } = useTheme();
  const corGrade = isDark ? "#27272a" : "#e4e4e7";
  const corTick = "#71717a"; // neutral-500: legível tanto no fundo claro quanto no escuro

  const porHora = new Map(horariosPico.map((h) => [h.hora, h.total_eventos]));
  const dados = Array.from({ length: 24 }, (_, hora) => ({
    hora: `${String(hora).padStart(2, "0")}h`,
    eventos: porHora.get(hora) || 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={dados} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
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
          cursor={{ fill: isDark ? "#27272a55" : "#e4e4e755" }}
          contentStyle={{
            background: isDark ? "#18181c" : "#ffffff",
            border: `1px solid ${corGrade}`,
            borderRadius: 8,
            fontSize: 12,
            color: isDark ? "#e4e4e7" : "#18181b",
          }}
          labelStyle={{ color: corTick }}
        />
        <Bar dataKey="eventos" name="Atendimentos" fill="#22d3ee" radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
