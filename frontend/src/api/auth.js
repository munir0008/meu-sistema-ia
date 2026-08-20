import { api } from "./client";

/** POST /api/auth/login — autentica o usuário e retorna { access_token, ... } */
export function login(email, senha) {
  return api.post("/api/auth/login", { email, senha }).then((r) => r.data);
}

/**
 * POST /api/auth/signup — autocadastro público: cria a empresa (status
 * `pending_payment`) e o primeiro usuário dela (ADMIN). SEM login automático —
 * a resposta não tem token, só `{ empresa_id, checkout_url }`: o chamador deve
 * redirecionar o navegador para `checkout_url` (Stripe Checkout) em seguida.
 */
export function signup({ nome_empresa, nome_admin, email, senha }) {
  return api.post("/api/auth/signup", { nome_empresa, nome_admin, email, senha }).then((r) => r.data);
}
