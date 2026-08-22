export function formatSegundosParaMinutos(segundos = 0) {
  const minutos = segundos / 60;
  if (minutos < 1) return `${Math.round(segundos)}s`;
  return `${minutos.toFixed(1)} min`;
}

export function formatDuracaoLonga(segundos = 0) {
  const totalMin = Math.floor(segundos / 60);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  const s = Math.round(segundos % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatPercent(valor = 0, casasDecimais = 0) {
  return `${valor.toFixed(casasDecimais)}%`;
}

export function formatDataHora(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// Produto simplificado 100% para varejo/supermercado — só "Balcão de Loja" é
// selecionável em câmera nova (o backend também restringe isso, ver
// schemas.CameraCreate/CameraUpdate). "escritorio"/"estoque" continuam aqui
// (não removidos do mapa) só para o rótulo de uma câmera ANTIGA já
// configurada com um desses perfis continuar aparecendo certo — eles não são
// mais oferecidos em nenhum formulário/dropdown de seleção.
export const PERFIL_CAMERA_LABELS = {
  balcao_loja: "Balcão de Loja",
  escritorio: "Escritório (legado)",
  estoque: "Estoque (legado)",
};

// Único ponto usado pelo dropdown de perfil no formulário de câmera — mesma
// ideia de TIPO_ZONA_OPCOES_SELECIONAVEIS abaixo.
export const PERFIL_CAMERA_OPCOES_SELECIONAVEIS = ["balcao_loja"];

// Idem: mantém "trabalho"/"neutra" pro RÓTULO/COR de uma zona antiga (de
// câmera com perfil escritorio/estoque) continuar renderizando certo onde já
// estiver desenhada — só não aparecem mais como opção pra criar zona nova
// (ver TIPO_ZONA_OPCOES_SELECIONAVEIS, usado no dropdown do ZoneEditor).
export const TIPO_ZONA_LABELS = {
  atendente: "Atendente",
  cliente: "Cliente",
  trabalho: "Trabalho (legado)",
  neutra: "Neutra (legado)",
};

// Único ponto usado pelo dropdown de "criar zona nova" (ZoneEditor) — produto
// simplificado 100% varejo/supermercado: só estes dois tipos podem ser
// desenhados. O backend aplica a mesma restrição (schemas.ZonaCreate).
export const TIPO_ZONA_OPCOES_SELECIONAVEIS = ["atendente", "cliente"];

/**
 * Classificação simples (heurística, sem capacidade configurada no backend) do nível
 * de movimentação da loja a partir da média de pessoas detectadas simultaneamente.
 */
export function nivelMovimentacao(mediaPessoas = 0) {
  if (mediaPessoas >= 5) return { label: "Alta", tone: "red" };
  if (mediaPessoas >= 2) return { label: "Média", tone: "amber" };
  return { label: "Baixa", tone: "emerald" };
}

export const TIPO_ZONA_CORES = {
  atendente: "#f97316", // laranja
  cliente: "#22c55e", // verde
  trabalho: "#f59e0b", // âmbar — legado, ver TIPO_ZONA_LABELS
  neutra: "#a1a1aa", // cinza — legado, ver TIPO_ZONA_LABELS
};

/** Rótulo e cor (tone do <Badge>) de cada status_assinatura da empresa. */
export const STATUS_ASSINATURA = {
  // Legado: cadastros de antes do pagamento virar obrigatório — não têm mais
  // acesso liberado (ver backend/auth.garantir_assinatura_ativa), daí o tone
  // vermelho apesar do rótulo antigo.
  trial: { label: "Bloqueada (trial legado)", tone: "red" },
  pending_payment: { label: "Pagamento pendente", tone: "amber" },
  active: { label: "Ativa", tone: "green" },
  past_due: { label: "Inadimplente", tone: "amber" },
  canceled: { label: "Cancelada", tone: "red" },
  unpaid: { label: "Inadimplente", tone: "red" },
};

export const PLANO_LABELS = {
  completo: "Plano Completo",
};

/** Rótulo do filtro rápido de período do Dashboard Analytics (ver PeriodoToggle). */
export const PERIODO_LABELS = {
  hoje: "hoje",
  "7d": "nos últimos 7 dias",
  "30d": "nos últimos 30 dias",
};
