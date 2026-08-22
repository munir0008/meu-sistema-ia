import { useEffect, useState } from "react";
import { FONTE_WEBCAM_NAVEGADOR } from "../../api/cameras";
import Button from "../ui/Button";
import ErrorBanner from "../ui/ErrorBanner";
import Input from "../ui/Input";
import Modal from "../ui/Modal";
import Select from "../ui/Select";
import { PERFIL_CAMERA_LABELS, PERFIL_CAMERA_OPCOES_SELECIONAVEIS } from "../../utils/format";

const VALOR_INICIAL = { nome_camera: "", rtsp_url: "0", perfil_ativo: "balcao_loja" };

function tipoFonteDoValor(rtspUrl) {
  return (rtspUrl || "").trim().toLowerCase() === FONTE_WEBCAM_NAVEGADOR ? "navegador" : "manual";
}

export default function CameraFormModal({ open, onClose, onSubmit, cameraEmEdicao }) {
  const [form, setForm] = useState(VALOR_INICIAL);
  // "manual": URL RTSP ou índice de webcam local digitado à mão.
  // "navegador": a própria aba do navegador de quem está vendo a câmera captura e envia — ver WebcamCapturePusher.
  const [tipoFonte, setTipoFonte] = useState("manual");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    if (open) {
      const inicial = cameraEmEdicao
        ? {
            nome_camera: cameraEmEdicao.nome_camera,
            rtsp_url: cameraEmEdicao.rtsp_url,
            perfil_ativo: cameraEmEdicao.perfil_ativo,
          }
        : VALOR_INICIAL;
      setForm(inicial);
      setTipoFonte(tipoFonteDoValor(inicial.rtsp_url));
      setErro(null);
    }
  }, [open, cameraEmEdicao]);

  function selecionarTipoFonte(tipo) {
    setTipoFonte(tipo);
    if (tipo === "navegador") {
      setForm((f) => ({ ...f, rtsp_url: FONTE_WEBCAM_NAVEGADOR }));
    } else if (form.rtsp_url.trim().toLowerCase() === FONTE_WEBCAM_NAVEGADOR) {
      setForm((f) => ({ ...f, rtsp_url: "0" }));
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    try {
      await onSubmit(form);
      onClose();
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível salvar a câmera.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={cameraEmEdicao ? "Editar Câmera" : "Nova Câmera"}>
      <form id="camera-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Nome da câmera"
          name="nome_camera"
          placeholder="Ex.: Balcão Principal"
          value={form.nome_camera}
          onChange={(e) => setForm({ ...form, nome_camera: e.target.value })}
          required
        />

        <Select
          label="Fonte do vídeo"
          value={tipoFonte}
          onChange={(e) => selecionarTipoFonte(e.target.value)}
        >
          <option value="manual">URL RTSP (câmera IP) ou webcam local de testes</option>
          <option value="navegador">Webcam deste navegador</option>
        </Select>

        {tipoFonte === "navegador" ? (
          <p className="-mt-2 text-xs text-neutral-500">
            A webcam de quem estiver com esta página aberta (aqui ou na tela de zonas) é capturada no
            navegador e enviada para o backend — funciona mesmo com o backend rodando na nuvem (Render).
            Mantenha a aba aberta e a permissão de câmera concedida para o feed continuar ao vivo.
          </p>
        ) : (
          <>
            <Input
              label='URL RTSP (ou "0" para webcam local de testes)'
              name="rtsp_url"
              placeholder="rtsp://usuario:senha@192.168.0.10:554/stream1"
              value={form.rtsp_url}
              onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
              required
            />
            <p className="-mt-2 text-xs text-neutral-500">
              Webcam local ("0", "1"...) só funciona quando o backend roda na mesma máquina que a câmera
              (ex.: <code>python run_app.py</code> local). Em produção (Render), o servidor não enxerga
              essa webcam — use uma URL RTSP de câmera IP acessível pela internet, ou escolha "Webcam
              deste navegador" acima.
            </p>
          </>
        )}

        <Select
          label="Perfil de análise"
          name="perfil_ativo"
          value={form.perfil_ativo}
          onChange={(e) => setForm({ ...form, perfil_ativo: e.target.value })}
        >
          {PERFIL_CAMERA_OPCOES_SELECIONAVEIS.map((valor) => (
            <option key={valor} value={valor}>
              {PERFIL_CAMERA_LABELS[valor]}
            </option>
          ))}
        </Select>

        <ErrorBanner>{erro}</ErrorBanner>
      </form>

      <div className="mt-5 flex justify-end gap-2 border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" form="camera-form" loading={salvando}>
          {cameraEmEdicao ? "Salvar alterações" : "Adicionar câmera"}
        </Button>
      </div>
    </Modal>
  );
}
