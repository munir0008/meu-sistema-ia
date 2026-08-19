import { AlertTriangle } from "lucide-react";

export default function ErrorBanner({ children, className = "" }) {
  if (!children) return null;
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-sm text-red-600 dark:text-red-300 ${className}`}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
