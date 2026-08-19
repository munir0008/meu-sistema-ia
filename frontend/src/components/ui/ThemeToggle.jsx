import { Moon, Sun } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";

/**
 * Seletor de tema claro/escuro — dois botões (não um switch único) para deixar a opção
 * atual explícita à primeira vista, útil logo na tela de login antes de haver contexto.
 */
export default function ThemeToggle({ className = "" }) {
  const { tema, setTema } = useTheme();

  const opcoes = [
    { valor: "light", rotulo: "Claro", Icon: Sun },
    { valor: "dark", rotulo: "Escuro", Icon: Moon },
  ];

  return (
    <div
      role="radiogroup"
      aria-label="Tema do sistema"
      className={`inline-flex items-center rounded-lg border border-neutral-200 bg-neutral-100 p-1 dark:border-neutral-800 dark:bg-neutral-900/60 ${className}`}
    >
      {opcoes.map(({ valor, rotulo, Icon }) => {
        const ativo = tema === valor;
        return (
          <button
            key={valor}
            type="button"
            role="radio"
            aria-checked={ativo}
            onClick={() => setTema(valor)}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 ${
              ativo
                ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-800 dark:text-neutral-50"
                : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
            }`}
          >
            <Icon className="size-3.5" />
            {rotulo}
          </button>
        );
      })}
    </div>
  );
}
