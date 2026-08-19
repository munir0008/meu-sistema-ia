import { api } from "./client";

/**
 * Equipe da própria empresa (contas USER) — restrito a ADMIN no backend
 * (require_roles(ADMIN)).
 */

export function listarEquipe() {
  return api.get("/api/empresa/usuarios").then((r) => r.data);
}

export function criarMembroEquipe({ nome, email, senha }) {
  return api.post("/api/empresa/usuarios", { nome, email, senha }).then((r) => r.data);
}

export function removerMembroEquipe(id) {
  return api.delete(`/api/empresa/usuarios/${id}`);
}
