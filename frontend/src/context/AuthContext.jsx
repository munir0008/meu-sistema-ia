import { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import { NOME_EMPRESA_STORAGE_KEY, TOKEN_STORAGE_KEY } from "../api/client";
import { decodeJwt, isTokenExpired } from "../utils/jwt";

const AuthContext = createContext(null);

export const ROLES = { SUPER_ADMIN: "SUPER_ADMIN", ADMIN: "ADMIN", USER: "USER" };

/** Para onde cada papel vai depois do login/cadastro (e para onde é mandado se tentar acessar a URL errada). */
export function rotaInicialPara(role) {
  return role === ROLES.SUPER_ADMIN ? "/admin" : "/dashboard";
}

function loadUserFromStorage() {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!token) return null;
  const payload = decodeJwt(token);
  if (!payload || isTokenExpired(payload)) {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(NOME_EMPRESA_STORAGE_KEY);
    return null;
  }
  return {
    token,
    usuarioId: payload.usuario_id,
    empresaId: payload.empresa_id ?? null,
    email: payload.sub,
    role: payload.role,
    nomeEmpresa: localStorage.getItem(NOME_EMPRESA_STORAGE_KEY) || "",
  };
}

function persistirSessao({ access_token, nome_empresa }) {
  localStorage.setItem(TOKEN_STORAGE_KEY, access_token);
  localStorage.setItem(NOME_EMPRESA_STORAGE_KEY, nome_empresa || "");
}

function respostaParaUsuario({ access_token, role, empresa_id, nome_empresa, status_assinatura }) {
  return {
    token: access_token,
    empresaId: empresa_id ?? null,
    role,
    nomeEmpresa: nome_empresa,
    statusAssinatura: status_assinatura ?? null,
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(loadUserFromStorage);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    // Revalida a sessão salva ao montar (ex.: token expirou enquanto a aba estava fechada).
    setUser(loadUserFromStorage());
  }, []);

  async function entrar(email, senha) {
    setCarregando(true);
    setErro(null);
    try {
      const resposta = await authApi.login(email, senha);
      persistirSessao(resposta);
      const novoUsuario = respostaParaUsuario(resposta);
      setUser(novoUsuario);
      return novoUsuario;
    } catch (err) {
      const detalhe = err?.response?.data?.detail || "Não foi possível entrar. Verifique email e senha.";
      setErro(detalhe);
      throw err;
    } finally {
      setCarregando(false);
    }
  }

  async function registrar(dadosCadastro) {
    setCarregando(true);
    setErro(null);
    try {
      const resposta = await authApi.signup(dadosCadastro);
      persistirSessao(resposta);
      const novoUsuario = respostaParaUsuario(resposta);
      setUser(novoUsuario);
      return novoUsuario;
    } catch (err) {
      const detalhe = err?.response?.data?.detail || "Não foi possível criar a conta. Tente novamente.";
      setErro(detalhe);
      throw err;
    } finally {
      setCarregando(false);
    }
  }

  function sair() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(NOME_EMPRESA_STORAGE_KEY);
    setUser(null);
  }

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isSuperAdmin: user?.role === ROLES.SUPER_ADMIN,
      isAdmin: user?.role === ROLES.ADMIN,
      carregando,
      erro,
      entrar,
      registrar,
      sair,
    }),
    [user, carregando, erro]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa ser usado dentro de <AuthProvider>");
  return ctx;
}
