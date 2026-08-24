import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, Text, View } from "react-native";

import { listarCameras, urlStreamCamera } from "@/api/cameras";
import CameraStreamView from "@/components/CameraStreamView";
import { useAuth } from "@/context/AuthContext";
import type { Camera } from "@/types/api";

export default function CamerasScreen() {
  const { sessao } = useAuth();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Sem useCallback de propósito — ver mesmo comentário em (tabs)/dashboard.tsx.
  async function carregar(opts?: { atualizando?: boolean }) {
    if (opts?.atualizando) setAtualizando(true);
    else setCarregando(true);
    setErro(null);
    try {
      const lista = await listarCameras();
      setCameras(lista);
    } catch {
      setErro("Não foi possível carregar as câmeras. Puxe pra baixo para tentar de novo.");
    } finally {
      setCarregando(false);
      setAtualizando(false);
    }
  }

  useEffect(() => {
    // Ver comentário equivalente em (tabs)/dashboard.tsx.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar();
  }, []);

  if (carregando) {
    return (
      <View className="flex-1 items-center justify-center bg-neutral-50 dark:bg-neutral-950">
        <ActivityIndicator color="#f97316" />
      </View>
    );
  }

  return (
    <FlatList
      className="flex-1 bg-neutral-50 dark:bg-neutral-950"
      contentContainerClassName="gap-3 p-4 pb-10"
      data={cameras}
      keyExtractor={(item) => String(item.id)}
      refreshControl={
        <RefreshControl refreshing={atualizando} onRefresh={() => carregar({ atualizando: true })} tintColor="#f97316" />
      }
      ListHeaderComponent={
        erro ? <Text className="pb-2 text-center text-sm text-red-500">{erro}</Text> : null
      }
      ListEmptyComponent={
        !erro ? (
          <Text className="py-10 text-center text-sm text-neutral-500 dark:text-neutral-400">
            Nenhuma câmera cadastrada ainda. Cadastre em Câmeras no painel web.
          </Text>
        ) : null
      }
      renderItem={({ item }) => (
        <View className="overflow-hidden rounded-2xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
          <CameraStreamView
            streamUrl={urlStreamCamera(item.id, sessao?.token ?? "")}
            altura={200}
          />
          <View className="flex-row items-center justify-between px-4 py-3">
            <Text className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
              {item.nome_camera}
            </Text>
            <View className="flex-row items-center gap-1.5">
              <View
                className={`size-2 rounded-full ${item.status === "online" ? "bg-emerald-500" : "bg-neutral-400"}`}
              />
              <Text className="text-xs text-neutral-500 dark:text-neutral-400">
                {item.status === "online" ? "Ao vivo" : "Offline"}
              </Text>
            </View>
          </View>
        </View>
      )}
    />
  );
}
