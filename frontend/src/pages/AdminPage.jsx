import { Ban, Building2, CheckCircle2, FileBarChart2, LayoutDashboard, Trash2, Video } from "lucide-react";
import { useEffect, useState } from "react";
import * as empresasApi from "../api/empresas";
import EmpresaCamerasTab from "../components/admin/EmpresaCamerasTab";
import EmpresaListSidebar from "../components/admin/EmpresaListSidebar";
import EmpresaBiPanel from "../components/dashboard/EmpresaBiPanel";
import CentralRelatorios from "../components/reports/CentralRelatorios";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ErrorBanner from "../components/ui/ErrorBanner";
import Spinner from "../components/ui/Spinner";
import { STATUS_ASSINATURA } from "../utils/format";

const ABAS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "cameras", label: "Câmeras & Zonas", icon: Video },
  { key: "relatorios", label: "Relatórios", icon: FileBarChart2 },
];

/**
 * Backoffice global do SUPER_ADMIN: lista de todas as empresas cadastradas no
 * SaaS à esquerda (com status financeiro e total de câmeras) e, à direita, o
 * dashboard/gerenciamento de câmeras+zonas+relatórios da empresa selecionada
 * — além de "Ativar/Suspender" a assinatura manualmente para suporte.
 */
export default function AdminPage() {
  const [empresas, setEmpresas] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [processando, setProcessando] = useState(false);

  const [empresaSelecionadaId, setEmpresaSelecionadaId] = useState(null);
  const [aba, setAba] = useState("dashboard");

  async function carregar(manterSelecao = true) {
    setCarregando(true);
    setErro(null);
    try {
      const lista = await empresasApi.listarEmpresas();
      setEmpresas(lista);
      if (!manterSelecao || !lista.some((e) => e.id === empresaSelecionadaId)) {
        setEmpresaSelecionadaId(lista[0]?.id ?? null);
      }
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível carregar as empresas.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function alternarAssinatura(empresa) {
    const novoStatus = empresa.status_assinatura === "active" ? "canceled" : "active";
    setProcessando(true);
    try {
      await empresasApi.atualizarEmpresa(empresa.id, { status_assinatura: novoStatus });
      await carregar();
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível atualizar a assinatura.");
    } finally {
      setProcessando(false);
    }
  }

  async function handleRemoverEmpresa(empresa) {
    if (!confirm(`Remover a empresa "${empresa.nome_empresa}"? Isso apaga também suas câmeras, usuários e métricas.`))
      return;
    try {
      await empresasApi.removerEmpresa(empresa.id);
      await carregar(false);
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível remover a empresa.");
    }
  }

  const empresaSelecionada = empresas.find((e) => e.id === empresaSelecionadaId);
  const status = empresaSelecionada
    ? STATUS_ASSINATURA[empresaSelecionada.status_assinatura] || STATUS_ASSINATURA.trial
    : null;

  return (
    <div className="flex flex-col gap-5 lg:flex-row">
      <EmpresaListSidebar
        empresas={empresas}
        empresaSelecionadaId={empresaSelecionadaId}
        onSelecionar={(id) => {
          setEmpresaSelecionadaId(id);
          setAba("dashboard");
        }}
      />

      <div className="min-w-0 flex-1">
        <ErrorBanner className="mb-4">{erro}</ErrorBanner>

        {carregando && <Spinner label="Carregando empresas…" />}

        {!carregando && empresas.length === 0 && !erro && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-neutral-300 py-16 text-center dark:border-neutral-800">
            <Building2 className="size-8 text-neutral-400 dark:text-neutral-700" />
            <p className="text-sm text-neutral-500">Nenhuma empresa cadastrada ainda.</p>
          </div>
        )}

        {!carregando && empresaSelecionada && (
          <div className="flex flex-col gap-5">
            <Card>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                      {empresaSelecionada.nome_empresa}
                    </p>
                    <Badge tone={status.tone} dot>
                      {status.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-neutral-500">
                    {empresaSelecionada.total_cameras} câmera(s) · plano{" "}
                    {empresaSelecionada.plano_atual || "nenhum"}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex gap-1 rounded-lg border border-neutral-200 bg-neutral-100 p-1 dark:border-neutral-800 dark:bg-neutral-950">
                    {ABAS.map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => setAba(key)}
                        className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                          aba === key
                            ? "bg-cyan-500/10 text-cyan-500 dark:text-cyan-400"
                            : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-300"
                        }`}
                      >
                        <Icon className="size-3.5" />
                        {label}
                      </button>
                    ))}
                  </div>

                  <Button
                    variant="secondary"
                    size="sm"
                    icon={empresaSelecionada.status_assinatura === "active" ? Ban : CheckCircle2}
                    loading={processando}
                    onClick={() => alternarAssinatura(empresaSelecionada)}
                  >
                    {empresaSelecionada.status_assinatura === "active" ? "Suspender" : "Ativar"}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    icon={Trash2}
                    onClick={() => handleRemoverEmpresa(empresaSelecionada)}
                  />
                </div>
              </div>
            </Card>

            {aba === "dashboard" && <EmpresaBiPanel empresaId={empresaSelecionada.id} />}
            {aba === "cameras" && <EmpresaCamerasTab empresaId={empresaSelecionada.id} />}
            {aba === "relatorios" && <CentralRelatorios empresaId={empresaSelecionada.id} />}
          </div>
        )}
      </div>
    </div>
  );
}
