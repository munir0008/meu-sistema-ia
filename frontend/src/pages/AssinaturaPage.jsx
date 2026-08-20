import { CalendarClock, CreditCard, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import * as empresasApi from "../api/empresas";
import * as paymentsApi from "../api/payments";
import PricingSection from "../components/landing/PricingSection";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ErrorBanner from "../components/ui/ErrorBanner";
import Spinner from "../components/ui/Spinner";
import { useAuth } from "../context/AuthContext";
import { formatDataHora, PLANO_LABELS, STATUS_ASSINATURA } from "../utils/format";

/**
 * Página de Assinatura: única rota de negócio acessível mesmo com a empresa
 * bloqueada (ver interceptor 403 em api/client.js) — mostra o status atual e
 * deixa escolher/trocar de plano via Stripe Checkout, ou gerenciar a
 * assinatura existente via Customer Portal.
 */
export default function AssinaturaPage() {
  const { isAdmin } = useAuth();
  const [searchParams] = useSearchParams();
  const checkoutStatus = searchParams.get("checkout"); // "sucesso" | "cancelado" | null

  const [empresa, setEmpresa] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [acaoCarregando, setAcaoCarregando] = useState(null); // chave do plano, "portal" ou null

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      setEmpresa(await empresasApi.minhaEmpresa());
    } catch (err) {
      setErro(err?.response?.data?.detail || "Não foi possível carregar sua assinatura.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
  }, []);

  async function assinarPlano(planoChave) {
    setAcaoCarregando(planoChave);
    setErro(null);
    try {
      const checkoutUrl = await paymentsApi.criarCheckoutSession(planoChave);
      window.location.href = checkoutUrl;
    } catch (err) {
      setErro(err?.response?.data?.detail || "Stripe ainda não configurado. Tente novamente mais tarde.");
      setAcaoCarregando(null);
    }
  }

  async function gerenciarAssinatura() {
    setAcaoCarregando("portal");
    setErro(null);
    try {
      const resposta = await paymentsApi.abrirPortalCliente();
      const destino = resposta?.portal_url || resposta?.checkout_url;
      if (!destino) {
        // DEBUG temporário: back respondeu 2xx mas sem URL — loga o corpo
        // cru pra investigar no console do navegador (F12) enquanto
        // diagnosticamos o "Não foi possível abrir o portal" em produção.
        console.error("[assinatura] customer-portal sem portal_url/checkout_url:", resposta);
        throw new Error("resposta sem URL");
      }
      // Sem stripe_customer_id válido, o backend devolve checkout_url em vez
      // de portal_url — redireciona do mesmo jeito, direto pro 1º pagamento.
      window.location.href = destino;
    } catch (err) {
      // DEBUG temporário: loga o erro completo (status, detail, mensagem de
      // rede) pra conseguirmos ver no console do navegador o que está
      // realmente falhando, já que a UI só mostra uma mensagem genérica.
      console.error("[assinatura] falha ao abrir portal/checkout:", err?.response?.status, err?.response?.data, err);
      setErro(err?.response?.data?.detail || "Não foi possível abrir o portal de assinatura. Tente novamente em instantes.");
      setAcaoCarregando(null);
    }
  }

  if (carregando) return <Spinner label="Carregando assinatura…" />;
  if (erro && !empresa) return <ErrorBanner>{erro}</ErrorBanner>;
  if (!empresa) return null;

  const status = STATUS_ASSINATURA[empresa.status_assinatura] || STATUS_ASSINATURA.pending_payment;
  const temAssinaturaStripe = !!empresa.stripe_customer_id;

  return (
    <div className="flex flex-col gap-6">
      {checkoutStatus === "sucesso" && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2.5 text-sm text-emerald-600 dark:text-emerald-300">
          Pagamento confirmado! Pode levar alguns segundos até o status abaixo atualizar.
        </div>
      )}
      {checkoutStatus === "cancelado" && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-600 dark:text-amber-300">
          Checkout cancelado — nenhuma cobrança foi feita.
        </div>
      )}

      <ErrorBanner>{erro}</ErrorBanner>

      <Card title="Sua assinatura" subtitle={empresa.nome_empresa}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Badge tone={status.tone} dot>
                {status.label}
              </Badge>
              {empresa.plano_atual && (
                <span className="text-sm text-neutral-600 dark:text-neutral-300">
                  Plano {PLANO_LABELS[empresa.plano_atual] || empresa.plano_atual}
                </span>
              )}
            </div>
            {empresa.data_fim_periodo && (
              <p className="flex items-center gap-1.5 text-xs text-neutral-500">
                <CalendarClock className="size-3.5" />
                {empresa.status_assinatura === "trial" ? "Trial expira em" : "Renova em"}{" "}
                {formatDataHora(empresa.data_fim_periodo)}
              </p>
            )}
          </div>

          {isAdmin && temAssinaturaStripe && (
            <Button icon={CreditCard} loading={acaoCarregando === "portal"} onClick={gerenciarAssinatura}>
              Gerenciar Assinatura
            </Button>
          )}
        </div>

        {!isAdmin && (
          <p className="mt-4 flex items-center gap-1.5 text-xs text-neutral-500">
            <ShieldAlert className="size-3.5" />
            Somente o ADMIN da empresa pode assinar ou gerenciar o pagamento.
          </p>
        )}
      </Card>

      {isAdmin && !temAssinaturaStripe && (
        <PricingSection onSelecionar={assinarPlano} carregandoChave={acaoCarregando} />
      )}
    </div>
  );
}
