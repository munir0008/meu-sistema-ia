import { useEffect, useState } from "react";
import Button from "../ui/Button";
import ErrorBanner from "../ui/ErrorBanner";
import Input from "../ui/Input";
import Modal from "../ui/Modal";
import Select from "../ui/Select";
import { PERFIL_CAMERA_LABELS } from "../../utils/format";

const VALOR_INICIAL = { nome_camera: "", rtsp_url: "0", perfil_ativo: "balcao_loja" };

export default function CameraFormModal({ open, onClose, onSubmit, cameraEmEdicao }) {
  const [form, setForm] = useState(VALOR_INICIAL);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    if (open) {
      setForm(
        cameraEmEdicao
          ? {
              nome_camera: cameraEmEdicao.nome_camera,
              rtsp_url: cameraEmEdicao.rtsp_url,
              perfil_ativo: cameraEmEdicao.perfil_ativo,
            }
          : VALOR_INICIAL
      );
      setErro(null);
    }
  }, [open, cameraEmEdicao]);

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
          (ex.: <code>python run_app.py</code> local). Em produção (Render), o servidor não enxerga sua
          webcam — use apenas uma URL RTSP de câmera IP acessível pela internet.
        </p>
        <Select
          label="Perfil de análise"
          name="perfil_ativo"
          value={form.perfil_ativo}
          onChange={(e) => setForm({ ...form, perfil_ativo: e.target.value })}
        >
          {Object.entries(PERFIL_CAMERA_LABELS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
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
