import { Building2, Video } from "lucide-react";
import { STATUS_ASSINATURA } from "../../utils/format";
import Badge from "../ui/Badge";

/** Lista de todas as empresas cadastradas no SaaS — backoffice do SUPER_ADMIN. */
export default function EmpresaListSidebar({ empresas, empresaSelecionadaId, onSelecionar }) {
  return (
    <div className="flex w-full flex-col gap-3 lg:w-72 lg:shrink-0">
      <p className="px-1 text-xs font-medium uppercase tracking-wide text-neutral-500">
        {empresas.length} {empresas.length === 1 ? "empresa" : "empresas"}
      </p>

      <div className="flex flex-col gap-1.5 overflow-y-auto lg:max-h-[calc(100vh-200px)]">
        {empresas.map((empresa) => {
          const ativa = empresa.id === empresaSelecionadaId;
          const status = STATUS_ASSINATURA[empresa.status_assinatura] || STATUS_ASSINATURA.pending_payment;
          return (
            <button
              key={empresa.id}
              onClick={() => onSelecionar(empresa.id)}
              className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                ativa
                  ? "border-cyan-500/40 bg-cyan-500/10"
                  : "border-neutral-200 bg-white hover:bg-neutral-100 dark:border-neutral-800 dark:bg-neutral-900/60 dark:hover:bg-neutral-900"
              }`}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                  <Building2 className="size-4" />
                </span>
                <div className="min-w-0">
                  <p
                    className={`truncate text-sm font-medium ${
                      ativa ? "text-cyan-600 dark:text-cyan-300" : "text-neutral-700 dark:text-neutral-200"
                    }`}
                  >
                    {empresa.nome_empresa}
                  </p>
                  <p className="flex items-center gap-1 truncate text-xs text-neutral-500">
                    <Video className="size-3" />
                    {empresa.total_cameras} câmera{empresa.total_cameras === 1 ? "" : "s"}
                  </p>
                </div>
              </div>

              <Badge tone={status.tone} dot className="shrink-0">
                {status.label}
              </Badge>
            </button>
          );
        })}
      </div>
    </div>
  );
}
