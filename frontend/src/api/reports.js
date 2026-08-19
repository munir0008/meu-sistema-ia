import { api } from "./client";

function extrairNomeArquivo(headers, fallback) {
  const disposicao = headers?.["content-disposition"];
  if (!disposicao) return fallback;
  const match = /filename="?([^";]+)"?/i.exec(disposicao);
  return match ? match[1] : fallback;
}

/**
 * O interceptor de erro do axios (client.js) espera `error.response.data.detail`,
 * mas com `responseType: "blob"` o corpo de uma resposta de ERRO (ex.: 403 JSON)
 * também chega como Blob, não como objeto já parseado — precisamos ler o texto e
 * fazer o parse manualmente para conseguir uma mensagem legível.
 */
async function extrairMensagemErro(err) {
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      const texto = await data.text();
      const json = JSON.parse(texto);
      return json.detail || "Não foi possível gerar o relatório.";
    } catch {
      return "Não foi possível gerar o relatório.";
    }
  }
  return data?.detail || "Não foi possível gerar o relatório.";
}

async function baixar(caminho, empresaId, inicio, fim, nomeFallback) {
  try {
    const resposta = await api.get(`${caminho}/${empresaId}`, {
      params: { data_inicio: inicio, data_fim: fim },
      responseType: "blob",
    });
    return {
      blob: resposta.data,
      nomeArquivo: extrairNomeArquivo(resposta.headers, nomeFallback),
    };
  } catch (err) {
    const mensagem = await extrairMensagemErro(err);
    throw new Error(mensagem);
  }
}

/** GET /api/reports/pdf/{empresa_id} — relatório executivo em PDF */
export function baixarRelatorioPdf(empresaId, inicio, fim) {
  return baixar("/api/reports/pdf", empresaId, inicio, fim, `relatorio-${inicio}-a-${fim}.pdf`);
}

/** GET /api/reports/excel/{empresa_id} — planilha multi-aba (.xlsx) */
export function baixarRelatorioExcel(empresaId, inicio, fim) {
  return baixar("/api/reports/excel", empresaId, inicio, fim, `relatorio-${inicio}-a-${fim}.xlsx`);
}

/** Dispara o download no navegador a partir do blob já obtido (sem servidor de arquivos). */
export function salvarBlobComoArquivo(blob, nomeArquivo) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
