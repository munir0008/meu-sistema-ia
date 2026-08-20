import { Check } from "lucide-react";
import { PLANOS } from "../../utils/planos";
import Button from "../ui/Button";

/**
 * Card do plano único da plataforma — reutilizado na Landing Page (visitante
 * é mandado para `/registrar`, que já cria a conta e redireciona pro Stripe
 * Checkout) e na página `/assinatura` (empresa já logada, o botão dispara o
 * Stripe Checkout direto).
 *
 * `carregandoChave`: chave do plano com ação em andamento (mostra spinner só
 * nesse botão). `textoBotao(plano)`: permite customizar o rótulo por contexto.
 */
export default function PricingSection({ onSelecionar, carregandoChave = null, textoBotao }) {
  const plano = PLANOS[0];

  return (
    <section id="precos" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-neutral-900 sm:text-3xl dark:text-neutral-50">
          Um plano só, sem letra miúda
        </h2>
        <p className="mt-3 text-sm text-neutral-600 sm:text-base dark:text-neutral-400">
          Assine em minutos. Cancele quando quiser, sem multa.
        </p>
      </div>

      <div className="mx-auto mt-12 max-w-md">
        <div className="flex flex-col gap-5 rounded-2xl border border-cyan-500/50 bg-cyan-500/5 p-8 shadow-lg shadow-cyan-500/10">
          <div>
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{plano.nome}</h3>
            <p className="mt-1 text-xs text-neutral-500">{plano.descricao}</p>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
              {plano.preco}
            </span>
            <span className="text-sm text-neutral-500">{plano.periodo}</span>
          </div>

          <ul className="flex flex-col gap-2.5">
            {plano.recursos.map((recurso) => (
              <li key={recurso} className="flex items-start gap-2 text-sm text-neutral-600 dark:text-neutral-300">
                <Check className="mt-0.5 size-4 shrink-0 text-cyan-500 dark:text-cyan-400" />
                {recurso}
              </li>
            ))}
          </ul>

          <Button
            className="w-full"
            loading={carregandoChave === plano.chave}
            onClick={() => onSelecionar(plano.chave)}
          >
            {textoBotao ? textoBotao(plano) : "Assinar Agora"}
          </Button>
        </div>
      </div>
    </section>
  );
}
