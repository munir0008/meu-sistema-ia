import InfoTooltip from "./InfoTooltip";

export default function KpiCard({ icon: Icon, label, value, hint, tone = "cyan", tooltip }) {
  const tones = {
    cyan: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
    indigo: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    red: "bg-red-500/10 text-red-600 dark:text-red-400",
  };

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900/60">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-medium text-neutral-500">
          {label}
          {tooltip && <InfoTooltip text={tooltip} />}
        </span>
        {Icon && (
          <span className={`flex size-8 items-center justify-center rounded-lg ${tones[tone]}`}>
            <Icon className="size-4" />
          </span>
        )}
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">{value}</p>
      {hint && <p className="mt-1 text-xs text-neutral-500">{hint}</p>}
    </div>
  );
}
