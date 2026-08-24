import "@/global.css";

import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { View } from "react-native";

import { AuthProvider, useAuth } from "@/context/AuthContext";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}

/**
 * Auth gate: usa Stack.Protected (Expo Router, padrão atual recomendado) —
 * "(tabs)" só é acessível com sessão ativa, "login" só sem sessão. Não
 * precisa de nenhum router.replace() manual: mudar `sessao` no AuthContext
 * (login/logout) já faz o guard reavaliar e o Router troca de rota sozinho.
 */
function RootNavigator() {
  const { sessao, hidratando } = useAuth();

  useEffect(() => {
    if (!hidratando) SplashScreen.hideAsync();
  }, [hidratando]);

  // Enquanto hidrata (lendo AsyncStorage no boot), mantém a splash nativa
  // visível em vez de "piscar" a tela de login antes de restaurar a sessão.
  if (hidratando) return <View className="flex-1 bg-white dark:bg-neutral-950" />;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!sessao}>
        <Stack.Screen name="(tabs)" />
      </Stack.Protected>

      <Stack.Protected guard={!sessao}>
        <Stack.Screen name="login" />
      </Stack.Protected>
    </Stack>
  );
}
