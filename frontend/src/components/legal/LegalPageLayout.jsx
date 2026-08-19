import LandingFooter from "../landing/LandingFooter";
import LandingNavbar from "../landing/LandingNavbar";

/**
 * Casca compartilhada pelas páginas jurídicas (/termos-de-uso,
 * /politica-de-privacidade): mesma navbar/rodapé da landing, conteúdo em
 * texto corrido estilizado à mão (sem plugin de tipografia do Tailwind).
 */
export default function LegalPageLayout({ titulo, atualizadoEm, children }) {
  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <LandingNavbar />

      <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 sm:text-3xl dark:text-neutral-50">
          {titulo}
        </h1>
        <p className="mt-2 text-xs text-neutral-500">Última atualização: {atualizadoEm}</p>

        <div
          className="mt-8 border-t border-neutral-200 pt-8
          [&_h2]:mb-2 [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-neutral-900
          [&_p]:mt-3 [&_p]:text-sm [&_p]:leading-relaxed [&_p]:text-neutral-600
          [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_ul]:text-sm [&_ul]:text-neutral-600
          [&_strong]:text-neutral-800
          dark:border-neutral-800 dark:[&_h2]:text-neutral-100 dark:[&_p]:text-neutral-400 dark:[&_ul]:text-neutral-400 dark:[&_strong]:text-neutral-200"
        >
          {children}
        </div>
      </main>

      <LandingFooter />
    </div>
  );
}
