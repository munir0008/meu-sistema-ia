const TONES = {
  neutral: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  green: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  red: "bg-red-500/10 text-red-600 dark:text-red-400",
  amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  cyan: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
};

export default function Badge({ children, tone = "neutral", dot = false, className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${TONES[tone]} ${className}`}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
