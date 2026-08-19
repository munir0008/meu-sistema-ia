import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(null);

const STORAGE_KEY = "visionsaas:theme";

function temaPreferidoDoSistema() {
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function carregarTemaInicial() {
  const salvo = localStorage.getItem(STORAGE_KEY);
  if (salvo === "light" || salvo === "dark") return salvo;
  return temaPreferidoDoSistema();
}

/**
 * Tema claro/escuro do sistema inteiro (não só do login): persiste em localStorage e
 * aplica a classe `.dark` na <html>, que é o que o Tailwind usa para resolver os
 * utilitários `dark:*` em todos os componentes (ver `@custom-variant dark` no index.css).
 * O flash inicial é evitado por um script inline equivalente em index.html.
 */
export function ThemeProvider({ children }) {
  const [tema, setTema] = useState(carregarTemaInicial);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", tema === "dark");
    root.style.colorScheme = tema;
    localStorage.setItem(STORAGE_KEY, tema);
  }, [tema]);

  const value = {
    tema,
    isDark: tema === "dark",
    setTema,
    alternarTema: () => setTema((atual) => (atual === "dark" ? "light" : "dark")),
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme precisa ser usado dentro de <ThemeProvider>");
  return ctx;
}
