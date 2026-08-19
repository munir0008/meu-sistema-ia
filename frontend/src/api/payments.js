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
 */
export function abrirPortalCliente() {
  return api.post("/api/payments/customer-portal").then((r) => r.data.portal_url);
}
