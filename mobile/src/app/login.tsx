import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "@/context/AuthContext";

export default function LoginScreen() {
  const { entrar, entrando, erro } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");

  async function handleEntrar() {
    if (!email.trim() || !senha) return;
    try {
      await entrar(email.trim(), senha);
      // Sem navegação manual aqui: Stack.Protected (ver app/_layout.tsx)
      // troca pra (tabs) sozinho assim que `sessao` deixa de ser null.
    } catch {
      // Erro já fica disponível em `erro` (AuthContext) pra exibir abaixo.
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      className="flex-1 bg-white dark:bg-neutral-950"
    >
      <View className="flex-1 justify-center gap-6 px-6">
        <View className="items-center gap-1">
          <Text className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">
            Inteligência de Loja
          </Text>
          <Text className="text-sm text-neutral-500 dark:text-neutral-400">
            Entre com a mesma conta do painel web
          </Text>
        </View>

        <View className="gap-3">
          <View className="gap-1">
            <Text className="text-xs font-medium text-neutral-600 dark:text-neutral-300">Email</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholder="voce@empresa.com"
              placeholderTextColor="#a3a3a3"
              className="rounded-lg border border-neutral-300 bg-neutral-50 px-3 py-2.5 text-neutral-900 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
            />
          </View>

          <View className="gap-1">
            <Text className="text-xs font-medium text-neutral-600 dark:text-neutral-300">Senha</Text>
            <TextInput
              value={senha}
              onChangeText={setSenha}
              secureTextEntry
              placeholder="••••••••"
              placeholderTextColor="#a3a3a3"
              className="rounded-lg border border-neutral-300 bg-neutral-50 px-3 py-2.5 text-neutral-900 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
              onSubmitEditing={handleEntrar}
            />
          </View>
        </View>

        {erro ? <Text className="text-center text-sm text-red-500">{erro}</Text> : null}

        <Pressable
          onPress={handleEntrar}
          disabled={entrando || !email.trim() || !senha}
          className="flex-row items-center justify-center gap-2 rounded-lg bg-orange-500 py-3 active:opacity-80 disabled:opacity-50"
        >
          {entrando ? <ActivityIndicator color="#fff" /> : null}
          <Text className="text-center font-semibold text-white">
            {entrando ? "Entrando..." : "Entrar"}
          </Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
