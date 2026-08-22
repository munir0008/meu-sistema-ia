import { RefreshCw, VideoOff } from "lucide-react";
import { useEffect, useState } from "react";
import { getVideoFeedUrl } from "../../api/cameras";
import Badge from "../ui/Badge";
import { PERFIL_CAMERA_LABELS } from "../../utils/format";
import WebcamCapturePusher from "./WebcamCapturePusher";

const RETRY_AUTOMATICO_MS = 5000;

export default function CameraCard({ camera }) {
  const [streamKey, setStreamKey] = useState(0);
  const [comErro, setComErro] = useState(false);
  const [pausado, setPausado] = useState(false);

  function reconectar() {
    setComErro(false);
    setStreamKey((k) => k + 1);
  }

  // Auto-retry: cobre o caso comum de o <img> ter sido montado ANTES da
  // câmera (ex.: webcam do navegador, ver WebcamCapturePusher) começar a
  // mandar frame — sem isso, o usuário ficaria preso na tela de erro até
  // clicar "Tentar novamente" na mão, mesmo com o feed já disponível.
  useEffect(() => {
    if (!comErro) return undefined;
    const t = setTimeout(reconectar, RETRY_AUTOMATICO_MS);
    return () => clearTimeout(t);
  }, [comErro]);

  return (
    <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900/60">
      <div className="relative aspect-video bg-black">
        {!pausado && !comErro && (
          <img
            key={streamKey}
            src={getVideoFeedUrl(camera.id)}
            alt={`Stream ao vivo de ${camera.nome_camera}`}
            className="h-full w-full object-contain"
            onError={() => setComErro(true)}
          />
        )}

        {(pausado || comErro) && (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-neutral-600">
            <VideoOff className="size-6" />
            <span className="text-xs">{comErro ? "Falha ao conectar à câmera" : "Streaming pausado"}</span>
            {comErro && (
              <button
                onClick={reconectar}
                className="mt-1 flex items-center gap-1.5 rounded-md border border-neutral-700 px-2.5 py-1 text-xs text-neutral-300 hover:bg-neutral-800"
              >
                <RefreshCw className="size-3.5" />
                Tentar novamente
              </button>
            )}
          </div>
        )}

        <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5">
          <Badge tone={camera.status === "online" ? "green" : "neutral"} dot>
            {camera.status === "online" ? (
              <span className="flex items-center gap-1">
                <span className="size-1.5 animate-pulse-live rounded-full bg-emerald-400" />
                AO VIVO
              </span>
            ) : (
              "OFFLINE"
            )}
          </Badge>
        </div>

        <button
          onClick={() => setPausado((p) => !p)}
          className="absolute right-2.5 top-2.5 rounded-md bg-black/60 px-2 py-1 text-[11px] font-medium text-neutral-200 hover:bg-black/80"
        >
          {pausado ? "Retomar" : "Pausar"}
        </button>
      </div>

      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">{camera.nome_camera}</p>
          <p className="text-xs text-neutral-500">{PERFIL_CAMERA_LABELS[camera.perfil_ativo] || camera.perfil_ativo}</p>
        </div>
        <Badge tone="cyan">Câmera #{camera.id}</Badge>
      </div>

      <WebcamCapturePusher camera={camera} onEnviando={reconectar} />
    </div>
  );
}
