import { ChevronDown } from "lucide-react";

export default function Select({ label, error, className = "", id, children, ...props }) {
  const selectId = id || props.name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={selectId} className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          className={`w-full appearance-none rounded-lg border bg-white px-3 py-2 pr-9 text-sm text-neutral-900
            outline-none transition-colors focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40
            dark:bg-neutral-900 dark:text-neutral-100
            ${error ? "border-red-500/50" : "border-neutral-300 dark:border-neutral-700"} ${className}`}
          {...props}
        >
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-neutral-500" />
      </div>
      {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
