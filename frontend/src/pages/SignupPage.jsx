import { Camera, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import ErrorBanner from "../components/ui/ErrorBanner";
import Input from "../components/ui/Input";
import ThemeToggle from "../components/ui/ThemeToggle";
import { useAuth } from "../context/AuthContext";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  const { registrar, carregando, erro } = useAuth();

  const [form, setForm] = useState({ nome_empresa: "", nome_admin: "", email: "", senha: "" });
  const [validacao, setValidacao] = useState({});
  const [redirecionandoParaCheckout, setRedirecionandoParaCheckout] = useState(false);

  function validar() {
    const proximosErros = {};
    if (!form.nome_empresa.trim()) proximosErros.nome_empresa = "Informe o nome da empresa.";
    if (!form.nome_admin.trim()) proximosErros.nome_admin = "Informe seu nome.";
    if (!form.email.trim()) proximosErros.email = "Informe o email.";
    else if (!EMAIL_REGEX.test(form.email.trim())) proximosErros.email = "Email inválido.";
    if (!form.senha) proximosErros.senha = "Informe uma senha.";
    else if (form.senha.length < 6) proximosErros.senha = "A senha deve ter ao menos 6 caracteres.";
    setValidacao(proximosErros);
    return Object.keys(proximosErros).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!validar()) return;
    try {
      // Sem login automático: a conta nasce com pagamento pendente (ver
      // AuthContext.registrar) — o único destino possível daqui é o Stripe
      // Checkout devolvido na própria resposta do cadastro.
      const { checkout_url } = await registrar(form);
      setRedirecionandoParaCheckout(true);
      window.location.href = checkout_url;
    } catch {
      // erro já fica exposto via useAuth().erro (inclui Stripe não configurado);
      // a conta já foi criada e pode ser retomada depois via login + /assinatura.
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-10 dark:bg-neutral-950">
      <div className="w-full max-w-sm">
        <div className="mb-4 flex justify-end">
          <ThemeToggle />
        </div>

        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <span className="flex size-11 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-500 dark:text-cyan-400">
            <Camera className="size-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-50">Crie sua conta</h1>
            <p className="text-sm text-neutral-500">Você será direcionado para o pagamento em seguida.</p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="flex flex-col gap-4 rounded-xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900/60"
        >
          <Input
            label="Nome da empresa"
            name="nome_empresa"
            placeholder="Ex.: Loja Modelo Ltda"
            value={form.nome_empresa}
            onChange={(e) => setForm({ ...form, nome_empresa: e.target.value })}
            error={validacao.nome_empresa}
          />
          <Input
            label="Seu nome"
            name="nome_admin"
            placeholder="Ex.: Maria Souza"
            value={form.nome_admin}
            onChange={(e) => setForm({ ...form, nome_admin: e.target.value })}
            error={validacao.nome_admin}
          />
          <Input
            label="Email"
            type="email"
            name="email"
            autoComplete="username"
            placeholder="voce@empresa.com"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            error={validacao.email}
          />
          <Input
            label="Senha"
            type="password"
            name="senha"
            autoComplete="new-password"
            placeholder="mínimo 6 caracteres"
            value={form.senha}
            onChange={(e) => setForm({ ...form, senha: e.target.value })}
            error={validacao.senha}
          />

          <ErrorBanner>{erro}</ErrorBanner>

          <p className="text-center text-[11px] leading-relaxed text-neutral-500">
            Ao criar sua conta, você concorda com os{" "}
            <Link to="/termos-de-uso" className="text-cyan-600 hover:underline dark:text-cyan-400">
              Termos de Uso
            </Link>{" "}
            e a{" "}
            <Link to="/politica-de-privacidade" className="text-cyan-600 hover:underline dark:text-cyan-400">
              Política de Privacidade
            </Link>
            .
          </p>

          <Button
            type="submit"
            icon={UserPlus}
            loading={carregando || redirecionandoParaCheckout}
            className="w-full"
          >
            {redirecionandoParaCheckout ? "Abrindo checkout…" : "Criar conta"}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-neutral-500">
          Já tem uma conta?{" "}
          <Link to="/login" className="text-cyan-600 hover:underline dark:text-cyan-400">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
