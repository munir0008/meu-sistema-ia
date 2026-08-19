/**
 * Cálculo de períodos para os filtros rápidos da Central de Relatórios.
 * Usa componentes de data LOCAIS (getFullYear/getMonth/getDate) em vez de
 * `toISOString()` — que converte para UTC e pode deslocar o dia em ±1 dependendo
 * do fuso horário do usuário, fazendo "Hoje" mostrar o dia errado.
 */
export const OPCOES_PERIODO = [
  { chave: "hoje", rotulo: "Hoje" },
  { chave: "ultimos7", rotulo: "Últimos 7 Dias" },
  { chave: "mes", rotulo: "Este Mês" },
  { chave: "personalizado", rotulo: "Período Personalizado" },
];

export function formatarDataLocal(data) {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

/**
 * Retorna { inicio, fim } (strings "YYYY-MM-DD") para a chave de período informada.
 * Para "personalizado", `intervaloPersonalizado` (já no mesmo formato) é repassado.
 */
export function calcularPeriodo(chave, intervaloPersonalizado) {
  const hoje = new Date();

  if (chave === "hoje") {
    const iso = formatarDataLocal(hoje);
    return { inicio: iso, fim: iso };
  }

  if (chave === "ultimos7") {
    const inicio = new Date(hoje);
    inicio.setDate(inicio.getDate() - 6);
    return { inicio: formatarDataLocal(inicio), fim: formatarDataLocal(hoje) };
  }

  if (chave === "mes") {
    const inicio = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
    return { inicio: formatarDataLocal(inicio), fim: formatarDataLocal(hoje) };
  }

  return intervaloPersonalizado;
}

export function formatarPeriodoLegivel({ inicio, fim }) {
  const fmt = (iso) => {
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
  };
  return inicio === fim ? fmt(inicio) : `${fmt(inicio)} a ${fmt(fim)}`;
}
