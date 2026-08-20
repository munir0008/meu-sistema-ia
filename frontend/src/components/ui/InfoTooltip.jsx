import { Info } from "lucide-react";

/**
 * Ícone "i" com tooltip explicativo ao passar o mouse ou focar via teclado —
 * usado ao lado de métricas menos óbvias (ex.: "Taxa de Ociosidade") nos
 * KpiCards do Dashboard Analytics. Tooltip em CSS puro (group-hover/
 * group-focus-within), sem lib de posicionamento.
 */
export default function InfoTooltip({ text }) {
  if (!text) return null;

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        className="flex size-4 items-center justify-center rounded-full text-neutral-400 outline-none transition-colors hover:text-neutral-600 focus-visible:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300 dark:focus-visible:text-neutral-300"
        aria-label="Mais informações"
      >
        <Info className="size-3.5" />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-56 -translate-x-1/2 rounded-lg border border-neutral-200 bg-white p-2.5 text-xs leading-snug font-normal normal-case text-neutral-600 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
      >
        {text}
      </span>
    </span>
  );
}
