import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useTheme } from "../../context/ThemeContext";

const CORES = ["#22d3ee", "#6366f1", "#f97316", "#22c55e", "#f59e0b", "#ec4899", "#a1a1aa"];

/**
 * Distribuição de atendimentos por câmera (`por_camera` do dashboard).
 * Nota: o backend hoje agrega métricas por câmera, não por tipo de zona
 * (atendente/cliente/trabalho) — para uma distribuição real por zona seria
 * necessário o backend gravar o tipo de zona na tabela de métricas.
 */
export default function DistribuicaoCamerasChart({ porCamera = {} }) {
  const { isDark } = useTheme();
  const dados = Object.values(porCamera)
    .map((c) => ({ nome: c.nome_camera, valor: c.total_atendimentos }))
    .filter((d) => d.valor > 0);

  if (dados.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-neutral-500">
        Sem atendimentos registrados hoje
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={dados}
          dataKey="valor"
          nameKey="nome"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          strokeWidth={0}
        >
          {dados.map((_, i) => (
            <Cell key={i} fill={CORES[i % CORES.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: isDark ? "#18181c" : "#ffffff",
            border: `1px solid ${isDark ? "#27272a" : "#e4e4e7"}`,
            borderRadius: 8,
            fontSize: 12,
            color: isDark ? "#e4e4e7" : "#18181b",
          }}
        />
        <Legend
          formatter={(value) => <span className="text-xs text-neutral-500 dark:text-neutral-400">{value}</span>}
          iconType="circle"
          iconSize={8}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
