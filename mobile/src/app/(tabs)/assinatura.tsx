import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, Text, View } from "react-native";

import { buscarMinhaEmpresa } from "@/api/empresa";
import { useAuth } from "@/context/AuthContext";
import type { Empresa } from "@/types/api";
import { formatDataCurta, PLANO_LABELS, STATUS_ASSINATURA_LABELS } from "@/utils/format";

/**
 * Tela de Assinatura — 100% READ-ONLY de propósito: mostra só o status que já
 * vem de GET /api/empresa/minha, SEM nenhum botão/link de checkout ou de
 * gestão de assinatura dentro do app. Isso não é uma limitação técnica — é
 * uma exigência das diretrizes da App Store/Google Play (compras de
 * assinatura digital feitas FORA do sistema de compra da própria loja de
 * apps, ou até um link "saia daqui pra pagar", podem levar a rejeição da
 * revisão — guideline 3.1.1 da Apple é a mais direta sobre isso). Gestão de
 * assinatura (assinar/trocar de plano/cancelar/portal do Stripe) continua
 * exclusiva do painel web (ver frontend/src/pages/AssinaturaPage.jsx) — daí
 * o aviso fixo no fim da tela.
 */
export default function AssinaturaScreen() {
  const { sessao } = useAuth();
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Sem useCallback de propósito — ver mesmo comentário em (tabs)/dashboard.tsx
  // (o React Compiler deste projeto já memoiza sozinho).
  async function carregar(opts?: { atualizando?: boolean }) {
    if (opts?.atualizando) setAtualizando(true);
    else setCarregando(true);
    setErro(null);
    try {
      const dados = await buscarMinhaEmpresa();
      setEmpresa(dados);
    } catch {
      setErro("Não foi possível carregar os dados da assinatura. Puxe pra baixo para tentar de novo.");
    } finally {
      setCarregando(false);
      setAtualizando(false);
    }
  }

  useEffect(() => {
    // react-hooks/set-state-in-effect: ver comentário equivalente em (tabs)/dashboard.tsx.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar();
  }, []);

  // SUPER_ADMIN não tem empresa própria (ver backend/routes.minha_empresa,
  // restrita a ADMIN/USER) — mesmo racional de (tabs)/dashboard.tsx.
  if (sessao?.role === "SUPER_ADMIN") {
    return (
      <View className="flex-1 items-center justify-center bg-white px-6 dark:bg-neutral-950">
        <Text className="text-center text-sm text-neutral-500 dark:text-neutral-400">
          Contas SUPER_ADMIN não têm uma empresa/assinatura associada.
        </Text>
      </View>
    );
  }

  const status = empresa ? STATUS_ASSINATURA_LABELS[empresa.status_assinatura] : null;
  const rotuloData = empresa?.status_assinatura === "trial" ? "Trial expira em" : "Próxima cobrança";

  return (
    <ScrollView
      className="flex-1 bg-neutral-50 dark:bg-neutral-950"
      contentContainerClassName="gap-4 p-4 pb-10"
      refreshControl={
        <RefreshControl refreshing={atualizando} onRefresh={() => carregar({ atualizando: true })} tintColor="#f97316" />
      }
    >
      <Text className="text-lg font-bold text-neutral-900 dark:text-neutral-50">Assinatura</Text>

      {carregando && (
        <View className="items-center py-10">
          <ActivityIndicator color="#f97316" />
        </View>
      )}

      {!carregando && erro && <Text className="py-10 text-center text-sm text-red-500">{erro}</Text>}

      {!carregando && empresa && status && (
        <View className="gap-3 rounded-2xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <View className="flex-row items-center justify-between">
            <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Empresa</Text>
            <Text className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {empresa.nome_empresa}
            </Text>
          </View>

          <View className="h-px bg-neutral-100 dark:bg-neutral-800" />

          <View className="flex-row items-center justify-between">
            <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Plano</Text>
            <Text className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {empresa.plano_atual ? PLANO_LABELS[empresa.plano_atual] : "—"}
            </Text>
          </View>

          <View className="flex-row items-center justify-between">
            <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Status</Text>
            <View className="flex-row items-center gap-1.5 rounded-full px-2.5 py-1" style={{ backgroundColor: `${status.cor}22` }}>
              <View className="size-1.5 rounded-full" style={{ backgroundColor: status.cor }} />
              <Text className="text-xs font-medium" style={{ color: status.cor }}>
                {status.label}
              </Text>
            </View>
          </View>

          {empresa.data_fim_periodo && (
            <View className="flex-row items-center justify-between">
              <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{rotuloData}</Text>
              <Text className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                {formatDataCurta(empresa.data_fim_periodo)}
              </Text>
            </View>
          )}

          <View className="flex-row items-center justify-between">
            <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Câmeras cadastradas</Text>
            <Text className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {empresa.total_cameras}
            </Text>
          </View>
        </View>
      )}

      {/* Aviso fixo — NUNCA um link/botão clicável pra checkout ou pro painel web
          (ver docstring do arquivo) — só texto informativo. */}
      <View className="flex-row items-start gap-2.5 rounded-2xl border border-orange-200 bg-orange-50 p-4 dark:border-orange-900/50 dark:bg-orange-950/30">
        <Ionicons name="information-circle" size={18} color="#f97316" style={{ marginTop: 1 }} />
        <Text className="flex-1 text-xs leading-5 text-orange-800 dark:text-orange-300">
          Para gerenciar ou assinar um plano, acesse o painel web pelo seu computador.
        </Text>
      </View>
    </ScrollView>
  );
}
