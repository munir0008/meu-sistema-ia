import { LogOut, ShieldCheck, User } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { ROLES, useAuth } from "../../context/AuthContext";
import ThemeToggle from "../ui/ThemeToggle";

const TITLES = {
  "/dashboard": "Dashboard",
  "/cameras": "Câmeras ao Vivo",
  "/reports": "Relatórios",
  "/equipe": "Equipe",
  "/assinatura": "Assinatura",
  "/admin": "Master Admin",
};

const MOBILE_NAV_EMPRESA = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/cameras", label: "Câmeras" },
  { to: "/reports", label: "Relatórios" },
  { to: "/assinatura", label: "Assinatura" },
];

export default function Topbar() {
  const { user, sair } = useAuth();
  const location = useLocation();
  const isSuperAdmin = user?.role === ROLES.SUPER_ADMIN;

  const titulo =
    TITLES[location.pathname] ||
    Object.entries(TITLES).find(([path]) => location.pathname.startsWith(path))?.[1] ||
    "VisionSaaS";

  return (
    <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/90 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/90">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{titulo}</h1>
          {isSuperAdmin && (
            <span className="flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-400">
              <ShieldCheck className="size-3" />
              SUPER_ADMIN
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {user?.nomeEmpresa && (
            <span className="hidden items-center gap-1.5 text-xs text-neutral-500 sm:flex">
              <User className="size-3.5" />
              {user.nomeEmpresa}
            </span>
          )}
          <ThemeToggle />
          <button
            onClick={sair}
            className="flex items-center gap-1.5 rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:border-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-neutral-200"
          >
            <LogOut className="size-3.5" />
            Sair
          </button>
        </div>
      </div>

      {!isSuperAdmin && (
        <nav className="flex gap-1 overflow-x-auto border-t border-neutral-200 px-3 py-2 lg:hidden dark:border-neutral-900">
          {MOBILE_NAV_EMPRESA.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `shrink-0 rounded-md px-3 py-1.5 text-xs font-medium ${
                  isActive
                    ? "bg-cyan-500/10 text-cyan-500 dark:text-cyan-400"
                    : "text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
