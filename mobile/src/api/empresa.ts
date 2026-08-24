import { api } from "./client";
import type { Empresa } from "@/types/api";

/**
 * GET /api/empresa/minha (schemas.EmpresaOut) — dados da PRÓPRIA empresa do
 * usuário logado (só ADMIN/USER; SUPER_ADMIN não tem empresa, ver
 * backend/routes.minha_empresa). Usado pela tela de Assinatura (read-only —
 * ver app/(tabs)/assinatura.tsx) e reaproveitável pra qualquer outra tela que
 * precise do nome da empresa/status de assinatura sem duplicar a chamada.
 */
export async function buscarMinhaEmpresa(): Promise<Empresa> {
  const { data } = await api.get<Empresa>("/api/empresa/minha");
  return data;
}
