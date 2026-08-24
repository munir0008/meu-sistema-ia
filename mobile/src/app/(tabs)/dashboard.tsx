import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { buscarDashboard, type PeriodoDashboard } from "@/api/dashboard";
import KpiCard from "@/components/KpiCard";
import { useAuth } from "@/context/AuthContext";
import type { DashboardMetrics } from "@/types/api";

const PERIODOS: { valor: PeriodoDashboard; rotulo: string }[] = [
  { valor: "hoje", rotulo: "Hoje" },
  { valor: "7d", rotulo: "7 dias" },
  { valor: "30d", rotulo: "30 dias" },
];

export default function DashboardScreen() {
  const { sessao, sair } = useAuth();
  const [periodo, setPeriodo] = useState<PeriodoDashboard>("hoje");
  const [dados, setDados] = useState<DashboardMetrics | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Sem useCallback de propósito: o React Compiler (ativo neste projeto, ver
  // app.json) já memoiza automaticamente — memoização manual aqui só entra
  // em conflito com a inferência dele (dependências narrowed como
  // `sessao?.empresaId` vs. o objeto `sessao` inteiro).
  async function carregar(opts?: { atualizando?: boolean }) {
    if (!sessao?.empresaId) return;
    if (opts?.atualizando) setAtualizando(true);
    else setCarregando(true);
    setErro(null);
    try {
      const resposta = await buscarDashboard(sessao.empresaId, periodo);
      setDados(resposta);
    } catch {
      setErro("Não foi possível carregar as métricas. Puxe pra baixo para tentar de novo.");
    } finally {
      setCarregando(false);
      setAtualizando(false);
    }
  }

  useEffect(() => {
    // react-hooks/set-state-in-effect: busca de dados no mount/troca de
    // dependências é o caso de uso canônico de useEffect (inclusive citado
    // como válido pela própria doc que a regra linka) — o mesmo padrão já
    // aparece sem supressão em src/hooks/use-color-scheme.web.ts, gerado
    // pelo template oficial do Expo (SDK 57) sem alteração nossa.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar();
    // `carregar` de propósito fora das deps: é recriada a cada render (sem
    // useCallback, ver comentário acima da função) — incluí-la faria o efeito
    // rodar em todo render, não só quando a empresa/período mudam.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessao?.empresaId, periodo]);

  // SUPER_ADMIN é uma conta global de operação da plataforma (sem empresa_id
  // próprio, ver models.Usuario/auth.py) — o dashboard de loja não se aplica
  // a ela; o app mobile é feito pra quem opera UMA loja (ADMIN/USER).
  if (!sessao?.empresaId) {
    return (
      <View className="flex-1 items-center justify-center gap-4 bg-white px-6 dark:bg-neutral-950">
        <Text className="text-center text-sm text-neutral-500 dark:text-neutral-400">
          O dashboard mobile é para contas de uma loja (ADMIN/USER). Esta conta (SUPER_ADMIN) não tem uma
          empresa associada — use o painel web para administração da plataforma.
        </Text>
        <Pressable onPress={sair} className="rounded-lg border border-neutral-300 px-4 py-2 dark:border-neutral-700">
          <Text className="text-sm text-neutral-700 dark:text-neutral-200">Sair</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView
      className="flex-1 bg-neutral-50 dark:bg-neutral-950"
      contentContainerClassName="gap-4 p-4 pb-10"
      refreshControl={
        <RefreshControl refreshing={atualizando} onRefresh={() => carregar({ atualizando: true })} tintColor="#f97316" />
      }
    >
      <View className="flex-row items-center justify-between">
        <View>
          <Text className="text-lg font-bold text-neutral-900 dark:text-neutral-50">{sessao.nomeEmpresa}</Text>
          <Text className="text-xs text-neutral-500 dark:text-neutral-400">Atendimento de balcão</Text>
        </View>
        <Pressable onPress={sair} hitSlop={8}>
          <Text className="text-xs text-neutral-400 underline">Sair</Text>
        </Pressable>
      </View>

      <View className="flex-row gap-2">
        {PERIODOS.map((p) => (
          <Pressable
            key={p.valor}
            onPress={() => setPeriodo(p.valor)}
            className={`rounded-full px-3 py-1.5 ${
              periodo === p.valor ? "bg-orange-500" : "bg-neutral-200 dark:bg-neutral-800"
            }`}
          >
            <Text
              className={`text-xs font-medium ${
                periodo === p.valor ? "text-white" : "text-neutral-600 dark:text-neutral-300"
              }`}
            >
              {p.rotulo}
            </Text>
          </Pressable>
        ))}
      </View>

      {carregando && (
        <View className="items-center py-10">
          <ActivityIndicator color="#f97316" />
        </View>
      )}

      {!carregando && erro && (
        <Text className="py-10 text-center text-sm text-red-500">{erro}</Text>
      )}

      {!carregando && dados && (
        <View className="flex-row flex-wrap gap-3">
          <KpiCard
            titulo="Clientes Atendidos"
            valor={String(dados.atendimentos_concluidos)}
            corAcento="#22c55e"
            subtitulo={`${dados.total_atendimentos} no total`}
          />
          <KpiCard
            titulo="Fila (Clientes)"
            valor={String(dados.fila.total_clientes_na_fila)}
            corAcento="#f97316"
            subtitulo={`espera média ${Math.round(dados.fila.tempo_medio_espera_segundos)}s`}
          />
          <KpiCard
            titulo="Desistências"
            valor={String(dados.fila.total_desistencias)}
            corAcento="#ef4444"
            subtitulo={`${dados.fila.taxa_desistencia_pct.toFixed(1)}% da fila`}
          />
          <KpiCard
            titulo="Ociosidade"
            valor={`${dados.equipe.taxa_ociosidade_balcao_pct.toFixed(1)}%`}
            corAcento="#a1a1aa"
            subtitulo="tempo do posto sem atendente"
          />
        </View>
      )}
    </ScrollView>
  );
}
