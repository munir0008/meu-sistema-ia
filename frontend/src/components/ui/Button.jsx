import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: "bg-cyan-500 text-neutral-950 hover:bg-cyan-400 focus-visible:outline-cyan-400",
  secondary:
    "bg-neutral-200 text-neutral-900 hover:bg-neutral-300 border border-neutral-300 focus-visible:outline-neutral-400 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700 dark:border-neutral-700 dark:focus-visible:outline-neutral-500",
  ghost:
    "bg-transparent text-neutral-600 hover:bg-neutral-200/60 focus-visible:outline-neutral-400 dark:text-neutral-300 dark:hover:bg-neutral-800/60 dark:focus-visible:outline-neutral-500",
  danger:
    "bg-red-500/10 text-red-600 hover:bg-red-500/20 border border-red-500/30 focus-visible:outline-red-500 dark:text-red-400 dark:focus-visible:outline-red-400",
};

const SIZES = {
  sm: "px-2.5 py-1.5 text-xs gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  icon: Icon,
  className = "",
  disabled,
  ...props
}) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
        ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon ? <Icon className="size-4" /> : null}
      {children}
    </button>
  );
}
