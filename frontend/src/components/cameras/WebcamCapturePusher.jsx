import { useEffect, useState } from "react";
import { FONTE_WEBCAM_NAVEGADOR, getCameraIngestWsUrl } from "../../api/cameras";

const INTERVALO_ENVIO_MS = 200; // ~5 fps de upload — o backend só reaproveita o frame mais recente
const QUALIDADE_JPEG = 0.7;
const LARGURA = 640;
const ALTURA = 480;

/**
 * Contrapartida de ENVIO de WebcamCapturePusher: quando `camera.rtsp_url ===
 * FONTE_WEBCAM_NAVEGADOR`, o backend não tem como abrir nenhuma webcam sozinho
 * (pode estar rodando num servidor remoto, ex.: Render, sem nenhuma câmera
 * física/virtual acessível) — então é o NAVEGADOR de quem está com a câmera na
 * frente que precisa capturar (getUserMedia) e empurrar os frames pro backend
 * via WebSocket (/api/camera_ingest). O <img> que exibe o resultado processado
 * (blur/zonas/overlay) continua vindo do /api/video_feed normal — este
 * componente só cuida do envio, não renderiza vídeo nenhum (por isso não some
 * da tela, mas também não ocupa espaço visual além do indicador de status).
 *
 * Fica montado enquanto a página estiver aberta: é essa aba do navegador que
 * atua como "ponte" entre a webcam física e o backend na nuvem — se ela
 * fechar, o feed para (ver CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS no backend).
 */
export default function WebcamCapturePusher({ camera }) {
  const [status, setStatus] = useState("conectando"); // conectando | enviando | erro
  const [mensagemErro, setMensagemErro] = useState(null);

  const ativo = camera && (camera.rtsp_url || "").trim().toLowerCase() === FONTE_WEBCAM_NAVEGADOR;

  useEffect(() => {
    if (!ativo) return undefined;

    let cancelado = false;
    let mediaStream = null;
    let ws = null;
    let intervalo = null;
    const video = document.createElement("video");
    const canvas = document.createElement("canvas");
    canvas.width = LARGURA;
    canvas.height = ALTURA;
    const ctx = canvas.getContext("2d");

    async function iniciar() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: LARGURA, height: ALTURA },
          audio: false,
        });
      } catch {
        if (!cancelado) {
          setStatus("erro");
          setMensagemErro("Não foi possível acessar sua webcam (permissão negada ou nenhuma câmera encontrada).");
        }
        return;
      }
      if (cancelado) {
        mediaStream.getTracks().forEach((t) => t.stop());
        return;
      }

      video.srcObject = mediaStream;
      video.muted = true;
      video.playsInline = true;
      try {
        await video.play();
      } catch {
        // Alguns navegadores exigem interação do usuário pra autoplay — o
        // elemento fica pronto mesmo assim assim que a página tiver o gesto.
      }

      ws = new WebSocket(getCameraIngestWsUrl(camera.id));
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        if (!cancelado) setStatus("enviando");
      };
      ws.onclose = () => {
        if (!cancelado) setStatus("conectando");
      };
      ws.onerror = () => {
        if (!cancelado) {
          setStatus("erro");
          setMensagemErro("Falha na conexão com o backend para enviar sua webcam.");
        }
      };

      intervalo = setInterval(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN || video.readyState < 2) return;
        ctx.drawImage(video, 0, 0, LARGURA, ALTURA);
        canvas.toBlob(
          (blob) => {
            if (blob && ws && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then((buf) => {
                if (ws && ws.readyState === WebSocket.OPEN) ws.send(buf);
              });
            }
          },
          "image/jpeg",
          QUALIDADE_JPEG
        );
      }, INTERVALO_ENVIO_MS);
    }

    iniciar();

    return () => {
      cancelado = true;
      if (intervalo) clearInterval(intervalo);
      if (ws) ws.close();
      if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ativo, camera?.id]);

  if (!ativo) return null;

  return (
    <div className="flex items-center gap-1.5 px-4 py-1.5 text-xs">
      <span className={`size-1.5 rounded-full ${status === "enviando" ? "animate-pulse-live bg-emerald-400" : status === "erro" ? "bg-red-500" : "bg-amber-400"}`} />
      {status === "erro" ? (
        <span className="text-red-500">{mensagemErro}</span>
      ) : status === "enviando" ? (
        <span className="text-emerald-600 dark:text-emerald-400">Enviando sua webcam para o backend</span>
      ) : (
        <span className="text-neutral-500">Conectando à sua webcam…</span>
      )}
    </div>
  );
}
