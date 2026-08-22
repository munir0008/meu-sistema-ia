import { useEffect, useRef, useState } from "react";
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
 * componente só cuida do envio.
 *
 * O <video> PRECISA estar de fato montado no DOM (não só criado em memória
 * com `document.createElement`) — em vários navegadores, principalmente
 * mobile, um <video> desanexado nunca avança o `readyState` de forma
 * confiável mesmo com a permissão concedida e a captura ativa (o ícone de
 * gravação da aba liga, mas o elemento nunca decodifica frame nenhum). Sem
 * isso, o loop de envio abaixo (que só desenha no canvas quando
 * `readyState >= 2`) nunca chega a rodar de verdade — e o pior: o WebSocket
 * abre normalmente, então o status antigo ("enviando", baseado só no
 * `ws.onopen`) mentia que estava tudo bem enquanto nenhum frame saía. Por
 * isso "enviando" aqui só é reportado depois do PRIMEIRO envio real.
 *
 * Fica montado enquanto a página estiver aberta: é essa aba do navegador que
 * atua como "ponte" entre a webcam física e o backend na nuvem — se ela
 * fechar, o feed para (ver CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS no backend).
 *
 * `onEnviando` (opcional) é chamado no primeiro frame REALMENTE enviado — o
 * sinal mais cedo possível de "o backend está recebendo dados agora". Quem
 * renderiza o <img> do /video_feed (CameraCard, ZoneEditor) usa isso pra
 * recarregar a imagem na hora, em vez de depender só do onError/retry.
 */
export default function WebcamCapturePusher({ camera, onEnviando }) {
  // conectando (pedindo câmera/abrindo WS) | aguardando (WS aberto, esperando
  // o <video> ficar pronto pra capturar) | enviando (já mandou frame de
  // verdade) | erro
  const [status, setStatus] = useState("conectando");
  const [mensagemErro, setMensagemErro] = useState(null);
  const videoRef = useRef(null);

  const ativo = camera && (camera.rtsp_url || "").trim().toLowerCase() === FONTE_WEBCAM_NAVEGADOR;

  useEffect(() => {
    // Log de diagnóstico SEMPRE, mesmo quando `ativo` é false — se o resto da
    // captura nunca aparece no console, é aqui que dá pra ver se o motivo é
    // simplesmente esta câmera não estar marcada como "browser" (ex.: rtsp_url
    // ainda "0"/RTSP manual) ou `camera` não ter chegado ainda.
    console.log(
      "[WebcamCapturePusher] montado — camera.id=%s rtsp_url=%o ativo=%s",
      camera?.id, camera?.rtsp_url, ativo
    );
    if (!ativo) return undefined;
    const video = videoRef.current; // capturado uma vez — evita ler .current de novo no cleanup (ref pode já ter mudado)
    if (!video) {
      console.warn("[WebcamCapturePusher] ativo=true mas videoRef.current é null — <video> não montou a tempo?");
      return undefined;
    }

    let cancelado = false;
    let mediaStream = null;
    let ws = null;
    let intervalo = null;
    let jaEnviouAlgumFrame = false;
    const canvas = document.createElement("canvas");
    canvas.width = LARGURA;
    canvas.height = ALTURA;
    const ctx = canvas.getContext("2d");

    async function iniciar() {
      console.log("[WebcamCapturePusher] chamando getUserMedia()...");
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: LARGURA, height: ALTURA },
          audio: false,
        });
      } catch (err) {
        console.error("[WebcamCapturePusher] Erro na conexão: getUserMedia falhou —", err);
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
      console.log("[WebcamCapturePusher] Webcam iniciada com sucesso — tracks:", mediaStream.getVideoTracks().map((t) => t.label));

      video.srcObject = mediaStream;
      try {
        await video.play();
      } catch (err) {
        // Alguns navegadores exigem um gesto do usuário pra autoplay — o
        // elemento fica pronto mesmo assim assim que a página tiver o gesto;
        // logamos pra facilitar diagnóstico se o vídeo nunca ficar pronto.
        console.warn("[WebcamCapturePusher] video.play() rejeitado (pode ser normal, ver comentário no código):", err);
      }

      setStatus("aguardando");

      const wsUrl = getCameraIngestWsUrl(camera.id);
      console.log("[WebcamCapturePusher] Tentando conectar WebSocket/Endpoint do backend...", wsUrl.replace(/token=[^&]+/, "token=***"));
      ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => console.log("[WebcamCapturePusher] WebSocket aberto — aguardando o <video> ficar pronto pra começar a enviar frames.");
      ws.onclose = (ev) => {
        console.log("[WebcamCapturePusher] WebSocket fechado — code=%s reason=%s", ev.code, ev.reason || "(sem motivo informado pelo servidor)");
        if (!cancelado) setStatus("conectando");
      };
      ws.onerror = (err) => {
        console.error("[WebcamCapturePusher] Erro na conexão: WebSocket —", err);
        if (!cancelado) {
          setStatus("erro");
          setMensagemErro("Falha na conexão com o backend para enviar sua webcam.");
        }
      };

      let tentativas = 0;
      intervalo = setInterval(() => {
        tentativas += 1;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        if (video.readyState < 2) {
          // HAVE_CURRENT_DATA — ainda não há frame decodificado pra capturar.
          // Só um aviso pontual em ~3s (não a cada 200ms) se isso nunca resolver.
          if (tentativas === 15) {
            console.warn(
              "[WebcamCapturePusher] video.readyState ainda é %s depois de ~3s com WS aberto — o <video> não está decodificando frames.",
              video.readyState
            );
          }
          return;
        }
        ctx.drawImage(video, 0, 0, LARGURA, ALTURA);
        canvas.toBlob(
          (blob) => {
            if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return;
            blob.arrayBuffer().then((buf) => {
              if (!ws || ws.readyState !== WebSocket.OPEN) return;
              ws.send(buf);
              if (!jaEnviouAlgumFrame) {
                jaEnviouAlgumFrame = true;
                console.log("[WebcamCapturePusher] primeiro frame enviado com sucesso —", buf.byteLength, "bytes.");
                if (!cancelado) {
                  setStatus("enviando");
                  onEnviando?.();
                }
              }
            });
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
      video.srcObject = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ativo, camera?.id]);

  if (!ativo) return null;

  return (
    <div className="flex items-center gap-1.5 px-4 py-1.5 text-xs">
      {/* Precisa estar de verdade no DOM pra decodificar frames de forma confiável
          entre navegadores (ver docstring acima) — por isso não é display:none,
          só reduzido a 1px e sem impacto visual/de interação. */}
      <video ref={videoRef} autoPlay muted playsInline aria-hidden="true" className="pointer-events-none absolute h-px w-px opacity-0" />

      <span
        className={`size-1.5 rounded-full ${
          status === "enviando" ? "animate-pulse-live bg-emerald-400" : status === "erro" ? "bg-red-500" : "bg-amber-400"
        }`}
      />
      {status === "erro" ? (
        <span className="text-red-500">{mensagemErro}</span>
      ) : status === "enviando" ? (
        <span className="text-emerald-600 dark:text-emerald-400">Enviando sua webcam para o backend</span>
      ) : status === "aguardando" ? (
        <span className="text-neutral-500">Aguardando a webcam ficar pronta para captura…</span>
      ) : (
        <span className="text-neutral-500">Conectando à sua webcam…</span>
      )}
    </div>
  );
}
