import { api } from "./client";

/**
 * POST /api/payments/create-checkout-session — cria uma sessão do Stripe
 * Checkout para o plano único da plataforma ("completo") e devolve a URL pra
 * onde redirecionar o navegador. Restrito a ADMIN no backend.
 */
export function criarCheckoutSession(plano) {
  return api.post("/api/payments/create-checkout-session", { plano }).then((r) => r.data.checkout_url);
}

/**
 * POST /api/payments/customer-portal — gera o link do Portal do Cliente da
 * Stripe (trocar cartão, ver faturas, cancelar). Restrito a ADMIN no backend.
 *
 * Se a empresa ainda não tiver (ou não tiver mais) um customer Stripe
 * válido, o backend não erra: devolve `checkout_url` em vez de `portal_url`
 * para o ADMIN fazer o primeiro pagamento. Devolve sempre os dois campos
 * (um deles null) — quem chama decide para onde redirecionar.
 */
export function abrirPortalCliente() {
  return api.post("/api/payments/customer-portal").then((r) => r.data);
}
