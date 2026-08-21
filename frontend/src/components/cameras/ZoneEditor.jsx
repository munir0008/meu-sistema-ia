import { Check, RotateCcw, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { getVideoFeedUrl } from "../../api/cameras";
import Button from "../ui/Button";
import Select from "../ui/Select";
import { TIPO_ZONA_CORES, TIPO_ZONA_LABELS } from "../../utils/format";
import WebcamCapturePusher from "./WebcamCapturePusher";

/**
 * Editor de zonas de interesse: desenha polígonos normalizados (0.0–1.0) sobre
 * o frame ao vivo da câmera. Clique adiciona vértices; "Finalizar zona" fecha o
 * polígono atual. O array `zonas` resultante já está no formato esperado pelo
 * backend (POST /api/admin/cameras/{id}/zonas).
 *
 * Recebe a câmera inteira (não só o id) porque, se for uma câmera de webcam do
 * navegador (rtsp_url === "browser"), esta própria página precisa capturar e
 * enviar os frames (ver WebcamCapturePusher) — do contrário não haveria
 * nenhuma imagem de referência aqui para desenhar as zonas em cima.
 */
export default function ZoneEditor({ camera, zonas, onChangeZonas }) {
  const cameraId = camera.id;
  const containerRef = useRef(null);
  const [tipoSelecionado, setTipoSelecionado] = useState("atendente");
  const [pontosAtuais, setPontosAtuais] = useState([]);

  function handleClickImagem(e) {
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    setPontosAtuais((pontos) => [...pontos, [Number(x.toFixed(4)), Number(y.toFixed(4))]]);
  }

  function finalizarZona() {
    if (pontosAtuais.length < 3) return;
    onChangeZonas([...zonas, { tipo_zona: tipoSelecionado, coordenadas: pontosAtuais }]);
    setPontosAtuais([]);
  }

  function cancelarDesenho() {
    setPontosAtuais([]);
  }

  function removerZona(index) {
    onChangeZonas(zonas.filter((_, i) => i !== index));
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="Tipo da próxima zona"
          value={tipoSelecionado}
          onChange={(e) => setTipoSelecionado(e.target.value)}
          className="w-48"
        >
          {Object.entries(TIPO_ZONA_LABELS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </Select>

        <Button type="button" variant="secondary" size="sm" icon={Check} onClick={finalizarZona} disabled={pontosAtuais.length < 3}>
          Finalizar zona ({pontosAtuais.length} pts)
        </Button>
        <Button type="button" variant="ghost" size="sm" icon={RotateCcw} onClick={cancelarDesenho} disabled={pontosAtuais.length === 0}>
          Cancelar desenho
        </Button>
      </div>

      <p className="text-xs text-neutral-500">
        Clique sobre a imagem para posicionar cada vértice do polígono (mínimo 3 pontos) e depois em
        &quot;Finalizar zona&quot;.
      </p>

      <WebcamCapturePusher camera={camera} />

      <div
        ref={containerRef}
        onClick={handleClickImagem}
        className="relative aspect-video w-full cursor-crosshair overflow-hidden rounded-lg border border-neutral-300 bg-black dark:border-neutral-800"
      >
        <img src={getVideoFeedUrl(cameraId)} alt="Referência para desenho de zonas" className="pointer-events-none h-full w-full object-contain" />

        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="pointer-events-none absolute inset-0 h-full w-full">
          {zonas.map((zona, i) => (
            <polygon
              key={i}
              points={zona.coordenadas.map(([x, y]) => `${x * 100},${y * 100}`).join(" ")}
              fill={`${TIPO_ZONA_CORES[zona.tipo_zona]}33`}
              stroke={TIPO_ZONA_CORES[zona.tipo_zona]}
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {pontosAtuais.length > 0 && (
            <polyline
              points={pontosAtuais.map(([x, y]) => `${x * 100},${y * 100}`).join(" ")}
              fill="none"
              stroke={TIPO_ZONA_CORES[tipoSelecionado]}
              strokeWidth={1}
              strokeDasharray="2 2"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {pontosAtuais.map(([x, y], i) => (
            <circle key={i} cx={x * 100} cy={y * 100} r={0.8} fill={TIPO_ZONA_CORES[tipoSelecionado]} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Zonas configuradas ({zonas.length})</p>
        {zonas.length === 0 && <p className="text-xs text-neutral-500">Nenhuma zona desenhada ainda.</p>}
        <ul className="flex flex-col gap-1.5">
          {zonas.map((zona, i) => (
            <li
              key={i}
              className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs dark:border-neutral-800 dark:bg-neutral-900/60"
            >
              <span className="flex items-center gap-2">
                <span className="size-2.5 rounded-full" style={{ backgroundColor: TIPO_ZONA_CORES[zona.tipo_zona] }} />
                {TIPO_ZONA_LABELS[zona.tipo_zona]}
                <span className="text-neutral-500">· {zona.coordenadas.length} pontos</span>
              </span>
              <button
                onClick={() => removerZona(i)}
                className="rounded-md p-1 text-neutral-500 hover:bg-neutral-200 hover:text-red-500 dark:hover:bg-neutral-800 dark:hover:text-red-400"
              >
                <Trash2 className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
