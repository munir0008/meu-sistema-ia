import { useNavigate } from "react-router-dom";
import FeaturesSection from "../components/landing/FeaturesSection";
import HeroSection from "../components/landing/HeroSection";
import LandingFooter from "../components/landing/LandingFooter";
import LandingNavbar from "../components/landing/LandingNavbar";
import PricingSection from "../components/landing/PricingSection";

/**
 * Landing page comercial (rota pública "/"). "Assinar Agora" leva ao cadastro
 * (`/registrar`) — o cadastro já redireciona direto para o Stripe Checkout
 * assim que a empresa/admin são criados, sem login automático (ver SignupPage).
 */
export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <LandingNavbar />
      <HeroSection />
      <FeaturesSection />
      <PricingSection onSelecionar={() => navigate("/registrar")} />
      <LandingFooter />
    </div>
  );
}
