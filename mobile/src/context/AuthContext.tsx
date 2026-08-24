import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";

import { login as loginApi } from "@/api/auth";
import { definirTokenApi } from "@/api/client";
import type { SessaoUsuario } from "@/types/api";

const CHAVE_STORAGE = "@meu-sistema-ia:sessao";

interface AuthContextValue {
  /** `null` = deslogado. Enquanto `hidratando` for true, ainda não sabemos o estado real. */
  sessao: SessaoUsuario | null;
  /** true só durante a leitura inicial do AsyncStorage no boot do app — evita "piscar" a tela de login. */
  hidratando: boolean;
  erro: string | null;
  entrando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function extrairMensagemErro(err: unknown): string {
  const resp = (err as { response?: { data?: { detail?: unknown } } } | undefined)?.response;
  const detail = resp?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message?: unknown }).message ?? "Falha ao entrar.");
  }
  if (!resp) return "Não foi possível conectar ao servidor. Verifique sua internet e a URL da API (ver README.md).";
  return "Não foi possível entrar. Tente novamente.";
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [sessao, setSessao] = useState<SessaoUsuario | null>(null);
  const [hidratando, setHidratando] = useState(true);
  const [entrando, setEntrando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Hidratação: restaura a sessão salva (se houver) assim que o app abre, pra
  // quem já logou antes não precisar digitar email/senha de novo toda vez.
  useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const bruto = await AsyncStorage.getItem(CHAVE_STORAGE);
        if (bruto && !cancelado) {
          const salva: SessaoUsuario = JSON.parse(bruto);
          definirTokenApi(salva.token);
          setSessao(salva);
        }
      } catch {
        // AsyncStorage corrompido/indisponível — trata como deslogado, não
        // trava o boot do app por causa disso.
      } finally {
        if (!cancelado) setHidratando(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  async function entrar(email: string, senha: string) {
    setEntrando(true);
    setErro(null);
    try {
      const resposta = await loginApi({ email, senha });
      const novaSessao: SessaoUsuario = {
        token: resposta.access_token,
        role: resposta.role,
        usuarioId: resposta.usuario_id,
        empresaId: resposta.empresa_id,
        nomeEmpresa: resposta.nome_empresa,
      };
      await AsyncStorage.setItem(CHAVE_STORAGE, JSON.stringify(novaSessao));
      definirTokenApi(novaSessao.token);
      setSessao(novaSessao);
    } catch (err) {
      setErro(extrairMensagemErro(err));
      throw err;
    } finally {
      setEntrando(false);
    }
  }

  async function sair() {
    await AsyncStorage.removeItem(CHAVE_STORAGE);
    definirTokenApi(null);
    setSessao(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({ sessao, hidratando, entrando, erro, entrar, sair }),
    [sessao, hidratando, entrando, erro]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>.");
  return ctx;
}
