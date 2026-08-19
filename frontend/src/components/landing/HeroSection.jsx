import { ArrowRight, PlayCircle } from "lucide-react";
import { Link } from "react-router-dom";
import Button from "../ui/Button";

export default function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-40 h-[480px] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-cyan-500/20 via-transparent to-transparent"
      />
      <div className="relative mx-auto flex max-w-4xl flex-col items-center gap-6 px-4 py-24 text-center sm:px-6 sm:py-32">
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-600 dark:text-cyan-400">
          Inteligência Operacional por Câmeras
        </span>
        <h1 className="text-4xl font-semibold tracking-tight text-neutral-900 sm:text-5xl dark:text-neutral-50">
          Transforme suas câmeras em{" "}
          <span className="bg-gradient-to-r from-cyan-500 to-indigo-500 bg-clip-text text-transparent">
            inteligência de negócio
          </span>
        </h1>
        <p className="max-w-2xl text-base text-neutral-600 sm:text-lg dark:text-neutral-400">
          Monitore atendimento, ocupação e produtividade em tempo real com detecção de pessoas por IA — com
          rostos e corpos anonimizados automaticamente (LGPD). Cadastre-se e comece a monitorar em minutos.
        </p>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <Link to="/registrar">
            <Button size="md" icon={ArrowRight} className="px-6">
              Começar Agora — 14 dias grátis
            </Button>
          </Link>
          <a href="#precos">
            <Button variant="secondary" size="md" icon={PlayCircle} className="px-6">
              Ver Planos
            </Button>
          </a>
        </div>
        <p className="text-xs text-neutral-500">Sem cartão de crédito para começar o teste.</p>
      </div>
    </section>
  );
}
