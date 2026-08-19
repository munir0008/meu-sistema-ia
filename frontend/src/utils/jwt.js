/**
 * Decodifica o payload de um JWT sem validar assinatura (a validação real é
 * sempre feita pelo backend). Usado apenas para extrair `usuario_id`,
 * `empresa_id`, `sub` (email) e `exp` para uso na UI.
 */
export function decodeJwt(token) {
  if (!token) return null;
  try {
    const [, payloadB64] = token.split(".");
    const normalized = payloadB64.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "="
    );
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isTokenExpired(payload) {
  if (!payload?.exp) return true;
  return Date.now() >= payload.exp * 1000;
}
