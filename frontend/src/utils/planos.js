/**
 * Plano único da plataforma — exibido na Landing Page e na página de
 * Assinatura. A chave precisa bater com `models.PlanoAssinatura` no backend
 * (ver STRIPE_PRICE_ID_UNICO em payments.py).
 */
export const PLANO_UNICO_CHAVE = "completo";

export const PLANOS = [
  {
    chave: PLANO_UNICO_CHAVE,
    nome: "Plano Completo",
    preco: "R$ 0,05",
    periodo: "/mês",
    descricao: "Tudo que sua operação precisa, em um único plano simples.",
    recursos: [
      "Câmeras ilimitadas",
      "Detecção de pessoas por IA (YOLOv8)",
      "Zonas de atendimento/ocupação",
      "Dashboard com métricas do dia",
      "Relatórios em PDF e Excel",
      "Usuários ilimitados na equipe",
      "Anonimização automática (LGPD)",
    ],
    destaque: true,
  },
];
