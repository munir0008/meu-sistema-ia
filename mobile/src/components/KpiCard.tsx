import { Text, View } from "react-native";

interface KpiCardProps {
  titulo: string;
  valor: string;
  corAcento?: string;
  subtitulo?: string;
}

/**
 * Card de métrica do dashboard — mesma ideia do KpiCard do painel web
 * (frontend/src/components/ui/KpiCard.jsx), simplificado pro mobile.
 */
export default function KpiCard({ titulo, valor, corAcento = "#f97316", subtitulo }: KpiCardProps) {
  return (
    <View
      className="min-w-[45%] flex-1 rounded-2xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900"
      style={{ borderLeftWidth: 4, borderLeftColor: corAcento }}
    >
      <Text className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{titulo}</Text>
      <Text className="mt-1 text-2xl font-bold text-neutral-900 dark:text-neutral-50">{valor}</Text>
      {subtitulo ? (
        <Text className="mt-0.5 text-[11px] text-neutral-400 dark:text-neutral-500">{subtitulo}</Text>
      ) : null}
    </View>
  );
}
