import { Navigate, useLocation } from "react-router-dom";
import { rotaInicialPara, useAuth } from "../../context/AuthContext";

/**
 * Guarda de rota do React (o pendant client-side do RBAC validado no backend):
 * - Sem sessão válida → manda para /login.
 * - Sessão válida mas papel fora de `roles` → NÃO deixa acessar a URL (ex.: um
 *   CLIENTE digitando /admin na barra de endereço) e redireciona para a home do
 *   próprio papel, em vez de mostrar a tela.
 */
export default function ProtectedRoute({ children, roles }) {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to={rotaInicialPara(user.role)} replace />;
  }

  return children;
}
