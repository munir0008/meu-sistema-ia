import { Camera, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../ui/Button";
import ThemeToggle from "../ui/ThemeToggle";

const LINKS = [
  { href: "#recursos", label: "Recursos" },
  { href: "#precos", label: "Preços" },
];

export default function LandingNavbar() {
  const [menuAberto, setMenuAberto] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-neutral-200 bg-white/80 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
            <Camera className="size-4" />
          </span>
          <span className="text-sm font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
            VisionSaaS
          </span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <ThemeToggle />
          <Link to="/login" className="text-sm font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100">
            Entrar
          </Link>
          <Link to="/registrar">
            <Button size="sm">Começar Agora</Button>
          </Link>
        </div>

        <button
          onClick={() => setMenuAberto((a) => !a)}
          className="rounded-md p-2 text-neutral-600 md:hidden dark:text-neutral-300"
        >
          {menuAberto ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {menuAberto && (
        <div className="flex flex-col gap-1 border-t border-neutral-200 px-4 py-3 md:hidden dark:border-neutral-800">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuAberto(false)}
              className="rounded-md px-2 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
            >
              {link.label}
            </a>
          ))}
          <div className="mt-2 flex items-center gap-2 px-2">
            <Link to="/login" className="flex-1 text-center text-sm font-medium text-neutral-600 dark:text-neutral-300">
              Entrar
            </Link>
            <Link to="/registrar" className="flex-1">
              <Button size="sm" className="w-full">
                Começar Agora
              </Button>
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
