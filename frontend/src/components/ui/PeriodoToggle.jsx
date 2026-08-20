const OPCOES = [
  { valor: "hoje", rotulo: "Hoje" },
  { valor: "7d", rotulo: "7 dias" },
  { valor: "30d", rotulo: "30 dias" },
];

/** Seletor rápido de intervalo (hoje/7 dias/30 dias) do Dashboard Analytics. */
export default function PeriodoToggle({ valor, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-200 p-0.5 dark:border-neutral-800">
      {OPCOES.map((opcao) => (
        <button
          key={opcao.valor}
          type="button"
          onClick={() => onChange(opcao.valor)}
          aria-pressed={valor === opcao.valor}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            valor === opcao.valor
              ? "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
              : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
          }`}
        >
          {opcao.rotulo}
        </button>
      ))}
    </div>
  );
}
