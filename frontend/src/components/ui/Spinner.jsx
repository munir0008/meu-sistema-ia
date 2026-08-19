import { Loader2 } from "lucide-react";

export default function Spinner({ label = "Carregando…", className = "" }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-10 text-sm text-neutral-500 ${className}`}>
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  );
}
