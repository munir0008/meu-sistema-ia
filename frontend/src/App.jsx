import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import DashboardLayout from "./components/layout/DashboardLayout";
import { AuthProvider, ROLES, rotaInicialPara, useAuth } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import AdminPage from "./pages/AdminPage";
import AssinaturaPage from "./pages/AssinaturaPage";
import DashboardPage from "./pages/DashboardPage";
import EquipePage from "./pages/EquipePage";
import LandingPage from "./pages/LandingPage";
import LiveCamerasPage from "./pages/LiveCamerasPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PoliticaPrivacidadePage from "./pages/PoliticaPrivacidadePage";
import ReportsPage from "./pages/ReportsPage";
import SignupPage from "./pages/SignupPage";
import TermosDeUsoPage from "./pages/TermosDeUsoPage";

/** "/" é a landing page pública para visitantes; usuário já logado é mandado direto pro próprio painel. */
function HomeOuLanding() {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <LandingPage />;
  return <Navigate to={rotaInicialPara(user.role)} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeOuLanding />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registrar" element={<SignupPage />} />
      <Route path="/termos-de-uso" element={<TermosDeUsoPage />} />
      <Route path="/politica-de-privacidade" element={<PoliticaPrivacidadePage />} />

      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        {/* SUPER_ADMIN: backoffice global — todas as empresas, câmeras, zonas e assinaturas */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute roles={[ROLES.SUPER_ADMIN]}>
              <AdminPage />
            </ProtectedRoute>
          }
        />

        {/* ADMIN/USER: painel isolado da própria empresa — CRUD completo de câmeras/zonas */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute roles={[ROLES.ADMIN, ROLES.USER]}>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cameras"
          element={
            <ProtectedRoute roles={[ROLES.ADMIN, ROLES.USER]}>
              <LiveCamerasPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute roles={[ROLES.ADMIN, ROLES.USER]}>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        {/* Único destino de negócio acessível mesmo com a assinatura bloqueada (ver api/client.js) */}
        <Route
          path="/assinatura"
          element={
            <ProtectedRoute roles={[ROLES.ADMIN, ROLES.USER]}>
              <AssinaturaPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/equipe"
          element={
            <ProtectedRoute roles={[ROLES.ADMIN]}>
              <EquipePage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ThemeProvider>
  );
}
