/// <reference types="nativewind/types" />

// TypeScript 6 (ver AGENTS.md) passou a exigir declaração explícita de módulo
// pra imports de efeito colateral (TS2882) — nativewind/types não declara
// "*.css" (isso historicamente vinha de fora), então declaramos aqui pra
// `import "@/global.css"` (ver app/_layout.tsx) parar de falhar o typecheck.
declare module "*.css";
