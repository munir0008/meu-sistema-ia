export default function Input({ label, error, className = "", id, ...props }) {
  const inputId = id || props.name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-neutral-900
          placeholder:text-neutral-400 outline-none transition-colors
          focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40
          dark:bg-neutral-900 dark:text-neutral-100 dark:placeholder:text-neutral-600
          ${error ? "border-red-500/50" : "border-neutral-300 dark:border-neutral-700"} ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
