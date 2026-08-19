import { Camera, LogIn } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/ui/Button";
import ErrorBanner from "../components/ui/ErrorBanner";
import Input from "../components/ui/Input";
import ThemeToggle from "../components/ui/ThemeToggle";
import { rotaInicialPara, useAuth } from "../context/AuthContext";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { entrar, carregando, erro } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [validacao, setValidacao] = useState({});

  function validar() {
    const proximosErros = {};
    if (!email.trim()) proximosErros.email = "Informe o email.";
    else if (!EMAIL_REGEX.test(email.trim())) proximosErros.email = "Email inválido.";
    if (!senha) proximosErros.senha = "Informe a senha.";
    else if (senha.length < 6) proximosErros.senha = "A senha deve ter ao menos 6 caracteres.";
    setValidacao(proximosErros);
    return Object.keys(proximosErros).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!validar()) return;
    try {
      const usuario = await entrar(email.trim(), senha);
      // Login unificado: o papel retornado pelo backend decide o destino.
      navigate(rotaInicialPara(usuario.role), { replace: true });
    } catch {
      // erro já fica exposto via useAuth().erro
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 dark:bg-neutral-950">
      <div className="w-full max-w-sm">
        <div className="mb-4 flex justify-end">
          <ThemeToggle />
        </div>

        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Link to="/" className="flex size-11 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
            <Camera className="size-5" />
          </Link>
          <div>
            <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-50">VisionSaaS</h1>
            <p className="text-sm text-neutral-500">Inteligência Operacional por Câmeras</p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="flex flex-col gap-4 rounded-xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900/60"
        >
          <Input
            label="Email"
            type="email"
            name="email"
            autoComplete="username"
            placeholder="voce@empresa.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={validacao.email}
          />
          <Input
            label="Senha"
            type="password"
            name="senha"
            autoComplete="current-password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            error={validacao.senha}
          />

          <ErrorBanner>{erro}</ErrorBanner>

          <Button type="submit" icon={LogIn} loading={carregando} className="mt-1 w-full">
            Entrar
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-neutral-500">
          Ainda não tem conta?{" "}
          <Link to="/registrar" className="text-cyan-600 hover:underline dark:text-cyan-400">
            Cadastre sua empresa
          </Link>
        </p>
      </div>
    </div>
  );
}
