import { Camera } from "lucide-react";
import { Link } from "react-router-dom";

export default function LandingFooter() {
  return (
    <footer className="border-t border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
            <Camera className="size-3.5" />
          </span>
          <span className="text-sm font-semibold text-neutral-900 dark:text-neutral-50">VisionSaaS</span>
          <span className="text-xs text-neutral-500">© {new Date().getFullYear()}</span>
        </div>

        <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-neutral-500">
          <a href="#recursos" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Recursos
          </a>
          <a href="#precos" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Preços
          </a>
          <a href="mailto:suporte@visionsaas.com" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Suporte
          </a>
          <Link to="/termos-de-uso" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Termos de Uso
          </Link>
          <Link to="/politica-de-privacidade" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Política de Privacidade
          </Link>
          <Link to="/login" className="hover:text-neutral-900 dark:hover:text-neutral-200">
            Entrar
          </Link>
        </nav>
      </div>
    </footer>
  );
}
