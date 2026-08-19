import EmpresaBiPanel from "../components/dashboard/EmpresaBiPanel";
import { useAuth } from "../context/AuthContext";

/** Painel da empresa (ADMIN/USER) — vídeo ao vivo, KPIs e gráficos do próprio dia. */
export default function DashboardPage() {
  const { user } = useAuth();
  return <EmpresaBiPanel empresaId={user.empresaId} />;
}
