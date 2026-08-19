import EmpresaCamerasTab from "../components/admin/EmpresaCamerasTab";
import { useAuth } from "../context/AuthContext";

/**
 * Câmeras da própria empresa (ADMIN/USER): CRUD completo (criar, editar,
 * remover) + editor de zonas — mesmo componente usado pelo SUPER_ADMIN no
 * backoffice, só que sempre escopado à empresa do usuário logado (o backend
 * garante o isolamento: nunca é possível enxergar câmeras de outra empresa).
 */
export default function LiveCamerasPage() {
  const { user } = useAuth();
  return <EmpresaCamerasTab empresaId={user.empresaId} />;
}
