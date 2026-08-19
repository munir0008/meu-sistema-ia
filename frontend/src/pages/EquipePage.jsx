import { Plus, Trash2, User as UserIcon, UserCog } from "lucide-react";
import { useEffect, useState } from "react";
import * as teamApi from "../api/team";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ErrorBanner from "../components/ui/ErrorBanner";
import Input from "../components/ui/Input";
import Modal from "../components/ui/Modal";
import Spinner from "../components/ui/Spinner";
import { useAuth } from "../context/AuthContext";

const VALOR_INICIAL = { nome: "", email: "", senha: "" };

/**
 * Equipe da empresa (só ADMIN): cria/remove contas USER, que têm o mesmo CRUD
 * de câmeras/zonas do ADMIN, mas não gerenciam equipe nem assinatura.
 */
export default function EquipePage() {
  const { user } = useAuth();
  const [membros, setMembros] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  const [modalAberto, setModalAberto] = useState(false);
  const [form, setForm] = useState(VALOR_INICIAL);
  const [salvando, setSalvando] = useState(false);
  const [erroForm, setErroForm] = useState(null);

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      setMembros(await teamApi.listarEquipe());
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível carregar a equipe.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
  }, []);

  function abrirModal() {
    setForm(VALOR_INICIAL);
    setErroForm(null);
    setModalAberto(true);
  }

  async function handleCriarMembro(e) {
    e.preventDefault();
    setSalvando(true);
    setErroForm(null);
    try {
      await teamApi.criarMembroEquipe(form);
      setModalAberto(false);
      await carregar();
    } catch (err) {
      setErroForm(err?.response?.data?.detail || "Não foi possível criar o usuário.");
    } finally {
      setSalvando(false);
    }
  }

  async function handleRemover(membro) {
    if (!confirm(`Remover o acesso de "${membro.nome || membro.email}"?`)) return;
    try {
      await teamApi.removerMembroEquipe(membro.id);
      await carregar();
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível remover o usuário.");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">
          Contas com acesso ao mesmo CRUD de câmeras e zonas da sua empresa (sem gerenciar equipe/assinatura).
        </p>
        <Button icon={Plus} onClick={abrirModal}>
          Novo Usuário
        </Button>
      </div>

      <ErrorBanner>{erro}</ErrorBanner>

      {carregando && <Spinner label="Carregando equipe…" />}

      <Card>
        <div className="flex flex-col divide-y divide-neutral-200 dark:divide-neutral-800">
          {!carregando && membros.length === 0 && (
            <p className="py-6 text-center text-sm text-neutral-500">Nenhum usuário adicionado ainda.</p>
          )}
          {membros.map((membro) => (
            <div key={membro.id} className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3">
                <span
                  className={`flex size-9 items-center justify-center rounded-lg ${
                    membro.role === "ADMIN"
                      ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                      : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
                  }`}
                >
                  {membro.role === "ADMIN" ? <UserCog className="size-4" /> : <UserIcon className="size-4" />}
                </span>
                <div>
                  <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {membro.nome || membro.email} · <span className="text-xs text-neutral-500">{membro.role}</span>
                  </p>
                  <p className="text-xs text-neutral-500">{membro.email}</p>
                </div>
              </div>
              {membro.role !== "ADMIN" && membro.id !== user.usuarioId && (
                <Button variant="danger" size="sm" icon={Trash2} onClick={() => handleRemover(membro)} />
              )}
            </div>
          ))}
        </div>
      </Card>

      <Modal open={modalAberto} onClose={() => setModalAberto(false)} title="Novo Usuário">
        <form id="equipe-form" onSubmit={handleCriarMembro} className="flex flex-col gap-4">
          <Input
            label="Nome"
            value={form.nome}
            onChange={(e) => setForm({ ...form, nome: e.target.value })}
            required
          />
          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <Input
            label="Senha"
            type="password"
            placeholder="mínimo 6 caracteres"
            value={form.senha}
            onChange={(e) => setForm({ ...form, senha: e.target.value })}
            minLength={6}
            required
          />
          <ErrorBanner>{erroForm}</ErrorBanner>
        </form>
        <div className="mt-5 flex justify-end gap-2 border-t border-neutral-200 pt-4 dark:border-neutral-800">
          <Button type="button" variant="ghost" onClick={() => setModalAberto(false)}>
            Cancelar
          </Button>
          <Button type="submit" form="equipe-form" loading={salvando}>
            Criar usuário
          </Button>
        </div>
      </Modal>
    </div>
  );
}
