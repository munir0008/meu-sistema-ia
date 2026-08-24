import axios from "axios";

// Mesmo fallback de produção usado pelo painel web (ver
// frontend/src/api/client.js) — rede de segurança pro app não ficar
// completamente morto (nenhuma tela carrega, sem nenhuma pista do motivo) só
// porque EXPO_PUBLIC_API_URL não foi definida num build (ex.: instalado via
// Expo Go sem `.env`, ou variável esquecida numa build EAS) — já aconteceu
// exatamente essa classe de bug com a variável equivalente do painel web
// (VITE_API_URL) em produção.
const API_URL_FALLBACK_PRODUCAO = "https://visionsaas-backend.onrender.com";

function resolverApiUrl(valorBruto: string | undefined): string {
  const valor = (valorBruto ?? "").trim();
  if (!valor) {
    console.warn(
      `[api] EXPO_PUBLIC_API_URL não definida — usando o fallback de produção (${API_URL_FALLBACK_PRODUCAO}). ` +
        "Para apontar pro backend local, crie mobile/.env com EXPO_PUBLIC_API_URL=http://SEU_IP_NA_REDE:8000 (ver README.md)."
    );
    return API_URL_FALLBACK_PRODUCAO;
  }
  if (!/^https?:\/\//i.test(valor)) {
    console.warn(`[api] EXPO_PUBLIC_API_URL inválida ("${valor}") — usando o fallback de produção.`);
    return API_URL_FALLBACK_PRODUCAO;
  }
  // Remove a barra final, se houver — evita "//api/..." nas URLs montadas
  // abaixo (client.ts usa baseURL + "/api/..." sempre com uma barra própria).
  return valor.replace(/\/+$/, "");
}

export const API_URL = resolverApiUrl(process.env.EXPO_PUBLIC_API_URL);

// `axios.create` é o uso oficial/documentado do pacote — falso positivo bem
// conhecido dessa regra especificamente com o axios.
// eslint-disable-next-line import/no-named-as-default-member
export const api = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

// Guarda o token em memória, sincronizado pelo AuthContext (login/logout/
// hidratação do AsyncStorage no boot do app) — o interceptor abaixo precisa
// ser síncrono, e o AsyncStorage não é, então não dá pra ler o token direto
// dele a cada requisição sem atrasar todas.
let tokenAtual: string | null = null;

export function definirTokenApi(token: string | null): void {
  tokenAtual = token;
}

api.interceptors.request.use((config) => {
  if (tokenAtual) {
    config.headers.set("Authorization", `Bearer ${tokenAtual}`);
  }
  return config;
});
