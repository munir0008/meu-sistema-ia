import { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { WebView } from "react-native-webview";

interface CameraStreamViewProps {
  /** URL de /api/video_feed/{id}?token=... (ver api/cameras.urlStreamCamera). */
  streamUrl: string;
  altura?: number;
}

/**
 * Exibe o stream MJPEG (multipart/x-mixed-replace) de uma câmera dentro de
 * uma WebView. Necessário porque o <Image> nativo do React Native (iOS/
 * Android) não decodifica um stream multipart contínuo — só entende UMA
 * imagem estática por resposta HTTP. O motor de navegador embutido na
 * WebView entende exatamente como um <img> de navegador desktop, que é o que
 * o painel web já usa pra essa mesma URL (ver
 * frontend/src/components/cameras/CameraCard.jsx).
 */
export default function CameraStreamView({ streamUrl, altura = 200 }: CameraStreamViewProps) {
  const [carregando, setCarregando] = useState(true);
  const [comErro, setComErro] = useState(false);
  const [tentativa, setTentativa] = useState(0);

  function reconectar() {
    setComErro(false);
    setCarregando(true);
    setTentativa((t) => t + 1);
  }

  const html = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
        <style>
          html, body { margin: 0; padding: 0; background: #000; height: 100%; overflow: hidden; }
          img { width: 100%; height: 100%; object-fit: contain; display: block; }
        </style>
      </head>
      <body>
        <img src="${streamUrl}" />
      </body>
    </html>
  `;

  return (
    <View style={{ height: altura }} className="overflow-hidden rounded-xl bg-black">
      {!comErro && (
        <WebView
          key={tentativa}
          source={{ html }}
          originWhitelist={["*"]}
          onLoadEnd={() => setCarregando(false)}
          onError={() => {
            setCarregando(false);
            setComErro(true);
          }}
          onHttpError={() => {
            setCarregando(false);
            setComErro(true);
          }}
          scrollEnabled={false}
          bounces={false}
          style={{ flex: 1, backgroundColor: "#000" }}
        />
      )}

      {carregando && !comErro && (
        <View className="absolute inset-0 items-center justify-center">
          <ActivityIndicator color="#f97316" />
        </View>
      )}

      {comErro && (
        <View className="absolute inset-0 items-center justify-center gap-2 px-4">
          <Text className="text-center text-xs text-neutral-300">Falha ao conectar à câmera</Text>
          <Pressable onPress={reconectar} className="rounded-md border border-neutral-600 px-3 py-1.5">
            <Text className="text-xs text-neutral-200">Tentar novamente</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
