import { Camera, CreditCard, FileBarChart2, LayoutDashboard, ShieldCheck, Users as UsersIcon, Video } from "lucide-react";
import { NavLink } from "react-router-dom";
import { ROLES, useAuth } from "../../context/AuthContext";

const NAV_EMPRESA = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/cameras", label: "Câmeras ao Vivo", icon: Video },
  { to: "/reports", label: "Relatórios", icon: FileBarChart2 },
];

const NAV_SUPER_ADMIN = [{ to: "/admin", label: "Empresas", icon: ShieldCheck }];

export default function Sidebar() {
  const { user, isAdmin } = useAuth();
  const isSuperAdmin = user?.role === ROLES.SUPER_ADMIN;
  const itens = isSuperAdmin ? NAV_SUPER_ADMIN : NAV_EMPRESA;

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-neutral-200 bg-white lg:flex dark:border-neutral-800 dark:bg-neutral-950">
      <div className="flex items-center gap-2 px-5 py-5">
        <span className="flex size-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
          <Camera className="size-4" />
        </span>
        <span className="text-sm font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          VisionSaaS
        </span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {itens.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-500 dark:text-cyan-400"
                  : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-neutral-200"
              }`
            }
          >
            <Icon className="size-4" />
            {label}
          </NavLink>
        ))}

        {!isSuperAdmin && isAdmin && (
          <NavLink
            to="/equipe"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-500 dark:text-cyan-400"
                  : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-neutral-200"
              }`
            }
          >
            <UsersIcon className="size-4" />
            Equipe
          </NavLink>
        )}

        {!isSuperAdmin && (
          <NavLink
            to="/assinatura"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-500 dark:text-cyan-400"
                  : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-900 dark:hover:text-neutral-200"
              }`
            }
          >
            <CreditCard className="size-4" />
            Assinatura
          </NavLink>
        )}
      </nav>

      <div className="border-t border-neutral-200 px-4 py-3 dark:border-neutral-800">
        <span className="rounded-md bg-neutral-100 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-neutral-500 dark:bg-neutral-900">
          {isSuperAdmin ? "Master Admin" : "Painel da Empresa"}
        </span>
      </div>
    </aside>
  );
}
