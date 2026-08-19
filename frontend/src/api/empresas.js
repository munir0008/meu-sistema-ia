import { api } from "./client";

/**
 * Backoffice de empresas (tenants do SaaS). Restrito a SUPER_ADMIN no backend
 * (require_roles(SUPER_ADMIN)) — usa o JWT normal, sem esquema à parte.
 */

export function listarEmpresas() {
  return api.get("/api/admin/empresas").then((r) => r.data);
}

export function atualizarEmpresa(id, payload) {
  return api.put(`/api/admin/empresas/${id}`, payload).then((r) => r.data);
}

export function removerEmpresa(id) {
  return api.delete(`/api/admin/empresas/${id}`);
}

/** GET /api/empresa/minha — dados de billing da própria empresa (ADMIN/USER). */
export function minhaEmpresa() {
  return api.get("/api/empresa/minha").then((r) => r.data);
}
