import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "../../context/ThemeContext";

/**
 * Dashboard Analytics Tópico 2 (Eficiência e Desempenho da Equipe) — distribuição
 * por horário: presença média de atendentes x clientes, a partir de
 * `equipe.distribuicao_por_hora` (amostragem periódica das zonas 'Atendente'/
 * 'Trabalho' e 'Cliente' — ver backend/models.AmostraBalcao).
 */
export default function PresencaPorHoraChart({ distribuicaoPorHora = [] }) {
  const { isDark } = useTheme();
  const corGrade = isDark ? "#27272a" : "#e4e4e7";
  const corTick = "#71717a"; // neutral-500: legível tanto no fundo claro quanto no escuro

  const porHora = new Map(distribuicaoPorHora.map((d) => [d.hora, d]));
  const dados = Array.from({ length: 24 }, (_, hora) => ({
    hora: `${String(hora).padStart(2, "0")}h`,
    atendentes: porHora.get(hora)?.media_atendentes_presentes || 0,
    clientes: porHora.get(hora)?.media_clientes_presentes || 0,
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
        <Legend
          formatter={(value) => <span className="text-xs text-neutral-500 dark:text-neutral-400">{value}</span>}
          iconType="circle"
          iconSize={8}
        />
        <Bar dataKey="atendentes" name="Atendentes (média)" fill="#f97316" radius={[4, 4, 0, 0]} maxBarSize={16} />
        <Bar dataKey="clientes" name="Clientes (média)" fill="#22d3ee" radius={[4, 4, 0, 0]} maxBarSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}
