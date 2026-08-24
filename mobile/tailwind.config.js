/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/app/**/*.{js,jsx,ts,tsx}", "./src/components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Mesmas cores de zona do painel web (ver TIPO_ZONA_CORES em
        // frontend/src/utils/format.js) — reaproveitadas aqui pros cards do
        // dashboard mobile ficarem visualmente consistentes com o web.
        atendente: "#f97316",
        cliente: "#22c55e",
      },
    },
  },
  plugins: [],
};
