import { useNavigate } from "react-router-dom";
import FeaturesSection from "../components/landing/FeaturesSection";
import HeroSection from "../components/landing/HeroSection";
import LandingFooter from "../components/landing/LandingFooter";
import LandingNavbar from "../components/landing/LandingNavbar";
import PricingSection from "../components/landing/PricingSection";

/**
 * Landing page comercial (rota pública "/"). "Assinar Agora" leva ao cadastro
 * já com o plano escolhido na URL (`/registrar?plano=...`) — o checkout do
 * Stripe só acontece depois do cadastro, já autenticado (ver SignupPage).
 */
export default function LandingPage() {
  const navigate = useNavigate();

  function selecionarPlano(chave) {
    navigate(`/registrar?plano=${chave}`);
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <LandingNavbar />
      <HeroSection />
      <FeaturesSection />
      <PricingSection onSelecionar={selecionarPlano} />
      <LandingFooter />
    </div>
  );
}
