import { Bell, Camera, ShieldCheck, Users } from "lucide-react";

const RECURSOS = [
  {
    icon: Camera,
    titulo: "Monitoramento por IA",
    descricao:
      "Detecção e rastreamento de pessoas em tempo real (YOLOv8 + ByteTrack) direto do stream das suas câmeras, sem hardware extra.",
  },
  {
    icon: ShieldCheck,
    titulo: "Zonas de Visão & LGPD",
    descricao:
      "Desenhe zonas de atendente, cliente, trabalho ou estoque direto sobre o vídeo — com rostos e corpos anonimizados automaticamente antes de qualquer exibição.",
  },
  {
    icon: Bell,
    titulo: "Métricas & Alertas",
    descricao:
      "Tempo de atendimento, horários de pico e ocupação calculados automaticamente, com relatórios executivos em PDF e Excel.",
  },
  {
    icon: Users,
    titulo: "Equipe & Multi-usuário",
    descricao:
      "Convide sua equipe para gerenciar câmeras e acompanhar métricas juntos, com isolamento total dos dados da sua empresa.",
  },
];

export default function FeaturesSection() {
  return (
    <section id="recursos" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-neutral-900 sm:text-3xl dark:text-neutral-50">
          Tudo que você precisa para operar com dados, não achismo
        </h2>
        <p className="mt-3 text-sm text-neutral-600 sm:text-base dark:text-neutral-400">
          Da câmera ao dashboard — sem instalar nada além de apontar a URL do stream.
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {RECURSOS.map(({ icon: Icon, titulo, descricao }) => (
          <div
            key={titulo}
            className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900/60"
          >
            <span className="flex size-10 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
              <Icon className="size-5" />
            </span>
            <h3 className="mt-4 text-sm font-semibold text-neutral-900 dark:text-neutral-100">{titulo}</h3>
            <p className="mt-1.5 text-sm text-neutral-500">{descricao}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
