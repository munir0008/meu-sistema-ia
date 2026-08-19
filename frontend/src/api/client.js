import axios from "axios";

// Fallback de produção como rede de segurança: se a env var VITE_API_URL não
// estiver definida no projeto da Vercel (ou vier vazia), cair em
// "http://localhost:8000" faz o navegador do usuário tentar falar com o
// localhost DELE, não com o backend — erro de rede, não de CORS, mas que
// aparece pro usuário como o mesmo "Não foi possível entrar" genérico. Em
// dev local, defina VITE_API_URL=http://localhost:8000 no seu ".env" (ver
// ".env.example") para não cair nesse fallback de produção sem querer.
const API_URL_FALLBACK_PRODUCAO = "https://visionsaas-backend.onrender.com";

export const API_URL = import.meta.env.VITE_API_URL || API_URL_FALLBACK_PRODUCAO;

export const TOKEN_STORAGE_KEY = "vision_saas_token";
// Nome da empresa não vem no JWT (não é usado para autorização) — guardado à parte
// só para continuar exibindo na UI (topbar etc.) depois de um refresh de página.
export const NOME_EMPRESA_STORAGE_KEY = "vision_saas_nome_empresa";

/**
 * Cliente axios único para toda a API, autenticada por JWT (SUPER_ADMIN, ADMIN ou
 * USER — o mesmo token serve para os três papéis; o backend decide o que cada um
 * pode fazer). O interceptor injeta automaticamente "Authorization: Bearer <token>"
 * e reage a dois status especiais:
 * - 401: token ausente/expirado/inválido — limpa a sessão e manda para o login.
 * - 403 com detail.code="subscription_required": a empresa não está em trial nem
 *   com assinatura ativa — manda para a página de planos em vez de deslogar
 *   (a sessão continua válida, só o acesso às rotas de negócio está bloqueado).
 */
export const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail;
    const url = error?.config?.url || "";
    const isLoginRequest = url.includes("/api/auth/login") || url.includes("/api/auth/signup");

    if (status === 401 && !isLoginRequest) {
      // Token ausente/expirado/inválido: limpa a sessão e manda para o login.
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(NOME_EMPRESA_STORAGE_KEY);
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
      return Promise.reject(error);
    }

    if (status === 403 && detail?.code === "subscription_required") {
      if (!window.location.pathname.startsWith("/assinatura")) {
        window.location.assign("/assinatura");
      }
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);
