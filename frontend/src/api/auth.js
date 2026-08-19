import { api } from "./client";

/** POST /api/auth/login — autentica o usuário e retorna { access_token, ... } */
export function login(email, senha) {
  return api.post("/api/auth/login", { email, senha }).then((r) => r.data);
}

/**
 * POST /api/auth/signup — autocadastro público: cria a empresa (em trial) e o
 * primeiro usuário dela (ADMIN), com login automático (mesmo formato de resposta
 * do login).
 */
export function signup({ nome_empresa, nome_admin, email, senha }) {
  return api.post("/api/auth/signup", { nome_empresa, nome_admin, email, senha }).then((r) => r.data);
}
