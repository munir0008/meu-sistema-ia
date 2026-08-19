import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-50 text-center dark:bg-neutral-950">
      <span className="flex size-12 items-center justify-center rounded-xl bg-neutral-100 text-neutral-500 dark:bg-neutral-900 dark:text-neutral-600">
        <Compass className="size-6" />
      </span>
      <div>
        <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Página não encontrada</h1>
        <p className="text-sm text-neutral-500">O endereço acessado não existe.</p>
      </div>
      <Link to="/" className="text-sm text-cyan-600 hover:underline dark:text-cyan-400">
        Voltar para o início
      </Link>
    </div>
  );
}
