import { ChevronDown, Pencil, Plus, Trash2, Video } from "lucide-react";
import { useEffect, useState } from "react";
import * as camerasApi from "../../api/cameras";
import { PERFIL_CAMERA_LABELS } from "../../utils/format";
import CameraFormModal from "../cameras/CameraFormModal";
import ZoneEditor from "../cameras/ZoneEditor";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ErrorBanner from "../ui/ErrorBanner";
import Spinner from "../ui/Spinner";

/**
 * Gerenciamento de câmeras e zonas de UMA empresa: CRUD completo de câmeras e
 * desenho de zonas. Reutilizado tanto pelo SUPER_ADMIN (aba "Câmeras" de
 * qualquer empresa no painel admin) quanto pela própria empresa (ADMIN/USER
 * em `/cameras`) — o isolamento entre empresas é sempre garantido pelo
 * backend, então este componente só precisa saber de qual empresa tratar.
 */
export default function EmpresaCamerasTab({ empresaId }) {
  const [cameras, setCameras] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  const [modalAberto, setModalAberto] = useState(false);
  const [cameraEmEdicao, setCameraEmEdicao] = useState(null);

  const [cameraExpandida, setCameraExpandida] = useState(null);
  const [zonasPorCamera, setZonasPorCamera] = useState({});
  const [salvandoZonas, setSalvandoZonas] = useState(false);
  const [erroZonas, setErroZonas] = useState(null);

  // `comSpinner=false` é usado pelo polling em segundo plano (ver useEffect
  // abaixo): sem essa distinção, o status.online/offline do badge (atualizado
  // pelo backend em tempo real conforme a câmera conecta — ver vision.py)
  // nunca chegaria na tela sem um F5, e a cada 5s a lista inteira piscaria
  // um spinner por cima de quem está desenhando zonas.
  async function carregar({ comSpinner = true } = {}) {
    if (comSpinner) {
      setCarregando(true);
      setErro(null);
    }
    try {
      setCameras(await camerasApi.listarCameras(empresaId));
    } catch (err) {
      if (comSpinner) setErro(err?.response?.data?.detail || "Não foi possível carregar as câmeras.");
    } finally {
      if (comSpinner) setCarregando(false);
    }
  }

  useEffect(() => {
    setCameraExpandida(null);
    setZonasPorCamera({});
    carregar();
    const intervalo = setInterval(() => carregar({ comSpinner: false }), 5_000);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empresaId]);

  function abrirNovaCamera() {
    setCameraEmEdicao(null);
    setModalAberto(true);
  }

  function abrirEdicaoCamera(camera) {
    setCameraEmEdicao(camera);
    setModalAberto(true);
  }

  async function handleSubmitCamera(form) {
    if (cameraEmEdicao) {
      await camerasApi.atualizarCamera(cameraEmEdicao.id, form);
    } else {
      await camerasApi.criarCamera({ ...form, empresa_id: empresaId });
    }
    await carregar();
  }

  async function handleRemoverCamera(camera) {
    if (!confirm(`Remover a câmera "${camera.nome_camera}"? Isso também apaga suas zonas.`)) return;
    try {
      await camerasApi.removerCamera(camera.id);
      await carregar();
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível remover a câmera.");
    }
  }

  async function toggleZonas(camera) {
    if (cameraExpandida === camera.id) {
      setCameraExpandida(null);
      return;
    }
    setCameraExpandida(camera.id);
    setErroZonas(null);
    if (!zonasPorCamera[camera.id]) {
      try {
        const zonas = await camerasApi.listarZonas(camera.id);
        setZonasPorCamera((atual) => ({
          ...atual,
          [camera.id]: zonas.map((z) => ({ tipo_zona: z.tipo_zona, coordenadas: z.coordenadas })),
        }));
      } catch (err) {
        setErroZonas(err?.response?.data?.detail || "Não foi possível carregar as zonas.");
      }
    }
  }

  function atualizarZonasLocal(cameraId, novasZonas) {
    setZonasPorCamera((atual) => ({ ...atual, [cameraId]: novasZonas }));
  }

  async function salvarZonas(cameraId) {
    setSalvandoZonas(true);
    setErroZonas(null);
    try {
      await camerasApi.salvarZonas(cameraId, zonasPorCamera[cameraId] || []);
    } catch (err) {
      setErroZonas(err?.response?.data?.detail || "Não foi possível salvar as zonas.");
    } finally {
      setSalvandoZonas(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">Cadastre câmeras e desenhe as zonas de interesse.</p>
        <Button icon={Plus} onClick={abrirNovaCamera}>
          Nova Câmera
        </Button>
      </div>

      <ErrorBanner>{erro}</ErrorBanner>

      {carregando && <Spinner label="Carregando câmeras…" />}

      {!carregando && cameras.length === 0 && !erro && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-neutral-300 py-16 text-center dark:border-neutral-800">
          <Video className="size-8 text-neutral-400 dark:text-neutral-700" />
          <p className="text-sm text-neutral-500">Nenhuma câmera cadastrada ainda.</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {cameras.map((camera) => {
          const expandida = cameraExpandida === camera.id;
          return (
            <div key={camera.id} className="rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900/60">
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                    <Video className="size-4" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">{camera.nome_camera}</p>
                    <p className="text-xs text-neutral-500">
                      {PERFIL_CAMERA_LABELS[camera.perfil_ativo]} · {camera.rtsp_url}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge tone={camera.status === "online" ? "green" : "neutral"} dot>
                    {camera.status}
                  </Badge>
                  <Button variant="secondary" size="sm" icon={Pencil} onClick={() => abrirEdicaoCamera(camera)}>
                    Editar
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={ChevronDown}
                    onClick={() => toggleZonas(camera)}
                    className={expandida ? "bg-neutral-300 dark:bg-neutral-700" : ""}
                  >
                    Zonas
                  </Button>
                  <Button variant="danger" size="sm" icon={Trash2} onClick={() => handleRemoverCamera(camera)} />
                </div>
              </div>

              {expandida && (
                <div className="border-t border-neutral-200 px-4 py-4 dark:border-neutral-800">
                  {!zonasPorCamera[camera.id] ? (
                    <Spinner label="Carregando zonas…" />
                  ) : (
                    <>
                      <ErrorBanner className="mb-3">{erroZonas}</ErrorBanner>
                      <ZoneEditor
                        camera={camera}
                        zonas={zonasPorCamera[camera.id]}
                        onChangeZonas={(novas) => atualizarZonasLocal(camera.id, novas)}
                      />
                      <div className="mt-4 flex justify-end">
                        <Button loading={salvandoZonas} onClick={() => salvarZonas(camera.id)}>
                          Salvar Zonas
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <CameraFormModal
        open={modalAberto}
        onClose={() => setModalAberto(false)}
        onSubmit={handleSubmitCamera}
        cameraEmEdicao={cameraEmEdicao}
      />
    </div>
  );
}
