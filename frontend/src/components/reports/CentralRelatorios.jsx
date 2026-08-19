import { CalendarRange, FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import * as reportsApi from "../../api/reports";
import { OPCOES_PERIODO, calcularPeriodo, formatarPeriodoLegivel } from "../../utils/periodo";
import Button from "../ui/Button";
import Card from "../ui/Card";
import ErrorBanner from "../ui/ErrorBanner";
import Input from "../ui/Input";
import Select from "../ui/Select";

/**
 * Central de Relatórios: filtro de período + exportação em PDF (executivo, com
 * gráfico e nota LGPD) ou Excel (3 abas: Resumo Diário, Log de Atendimentos,
 * Métricas de Ocupação). Reutilizada tanto no painel do cliente (`ReportsPage`)
 * quanto na aba do admin para o cliente selecionado (`AdminPage`).
 */
export default function CentralRelatorios({ empresaId }) {
  const [periodoChave, setPeriodoChave] = useState("hoje");
  const [personalizado, setPersonalizado] = useState(() => {
    const hoje = calcularPeriodo("hoje");
    return { inicio: hoje.inicio, fim: hoje.fim };
  });
  const [gerando, setGerando] = useState(null); // 'pdf' | 'excel' | null
  const [erro, setErro] = useState(null);

  const periodo = calcularPeriodo(periodoChave, personalizado);
  const periodoValido = periodo.inicio && periodo.fim && periodo.inicio <= periodo.fim;

  async function exportar(formato) {
    if (!periodoValido) {
      setErro("Selecione um período válido (data final não pode ser antes da inicial).");
      return;
    }
    setGerando(formato);
    setErro(null);
    try {
      const baixarFn = formato === "pdf" ? reportsApi.baixarRelatorioPdf : reportsApi.baixarRelatorioExcel;
      const { blob, nomeArquivo } = await baixarFn(empresaId, periodo.inicio, periodo.fim);
      reportsApi.salvarBlobComoArquivo(blob, nomeArquivo);
    } catch (err) {
      setErro(err.message || "Não foi possível gerar o relatório.");
    } finally {
      setGerando(null);
    }
  }

  return (
    <Card
      title="Central de Relatórios"
      subtitle="Exporte o relatório executivo em PDF ou a planilha detalhada em Excel"
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <Select
            label="Período"
            value={periodoChave}
            onChange={(e) => setPeriodoChave(e.target.value)}
            className="w-56"
          >
            {OPCOES_PERIODO.map((op) => (
              <option key={op.chave} value={op.chave}>
                {op.rotulo}
              </option>
            ))}
          </Select>

          {periodoChave === "personalizado" && (
            <>
              <Input
                label="De"
                type="date"
                value={personalizado.inicio}
                max={personalizado.fim}
                onChange={(e) => setPersonalizado((p) => ({ ...p, inicio: e.target.value }))}
              />
              <Input
                label="Até"
                type="date"
                value={personalizado.fim}
                min={personalizado.inicio}
                onChange={(e) => setPersonalizado((p) => ({ ...p, fim: e.target.value }))}
              />
            </>
          )}
        </div>

        <p className="flex items-center gap-1.5 text-xs text-neutral-500">
          <CalendarRange className="size-3.5" />
          {periodoValido ? `Exportando dados de ${formatarPeriodoLegivel(periodo)}` : "Selecione um período válido"}
        </p>

        <ErrorBanner>{erro}</ErrorBanner>

        <div className="flex flex-wrap gap-3">
          <Button
            icon={FileText}
            variant="secondary"
            loading={gerando === "pdf"}
            disabled={!periodoValido || gerando !== null}
            onClick={() => exportar("pdf")}
          >
            {gerando === "pdf" ? "Gerando relatório..." : "Baixar Relatório PDF"}
          </Button>
          <Button
            icon={FileSpreadsheet}
            loading={gerando === "excel"}
            disabled={!periodoValido || gerando !== null}
            onClick={() => exportar("excel")}
          >
            {gerando === "excel" ? "Gerando relatório..." : "Exportar Planilha Excel"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
