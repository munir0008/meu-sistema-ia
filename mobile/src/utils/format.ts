import type { StatusAssinatura, PlanoAssinatura } from "@/types/api";

/**
 * Mesmos rótulos/cores do painel web (ver STATUS_ASSINATURA em
 * frontend/src/utils/format.js) — mantidos em sincronia manualmente, igual
 * aos tipos em src/types/api.ts.
 */
export const STATUS_ASSINATURA_LABELS: Record<StatusAssinatura, { label: string; cor: string }> = {
  // Legado: cadastros de antes do pagamento virar obrigatório — não têm mais
  // acesso liberado (ver backend/auth.garantir_assinatura_ativa).
  trial: { label: "Bloqueada (trial legado)", cor: "#ef4444" },
  pending_payment: { label: "Pagamento pendente", cor: "#f59e0b" },
  active: { label: "Ativa", cor: "#22c55e" },
  past_due: { label: "Inadimplente", cor: "#f59e0b" },
  canceled: { label: "Cancelada", cor: "#ef4444" },
  unpaid: { label: "Inadimplente", cor: "#ef4444" },
};

export const PLANO_LABELS: Record<PlanoAssinatura, string> = {
  completo: "Plano Completo",
};

export function formatDataCurta(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
