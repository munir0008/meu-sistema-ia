# Passo a Passo — Publicar o VisionSaaS na Nuvem

Backend (FastAPI + Postgres) no **Render**, frontend (React/Vite) na **Vercel**,
pagamentos na **Stripe** e e-mails transacionais na **Resend**. Siga na ordem —
cada etapa depende da anterior.

---

## 0. Antes de começar

- [ ] Conta no [Render](https://render.com), na [Vercel](https://vercel.com), na [Stripe](https://dashboard.stripe.com) e na [Resend](https://resend.com).
- [ ] Este projeto em um repositório Git (GitHub/GitLab) — Render e Vercel publicam a partir de um repo, não de arquivos locais soltos.
  ```bash
  cd "meu-sistema-ia"
  git init
  git add .
  git commit -m "Deploy inicial"
  git branch -M main
  git remote add origin <URL_DO_SEU_REPOSITORIO>
  git push -u origin main
  ```

---

## 1. Backend no Render

O repo já tem `render.yaml` (raiz) e `backend/Procfile` prontos.

1. **Novo Blueprint**: Render Dashboard → **New** → **Blueprint** → selecione o repositório → Render lê o `render.yaml` sozinho e propõe criar:
   - o serviço web `visionsaas-backend` (Python, plano `free`)
   - o banco `visionsaas-db` (Postgres, plano `free`) — `DATABASE_URL` é injetada automaticamente, nada a fazer aqui.
2. Clique **Apply** e aguarde o primeiro build (instala `requirements.txt` — pode levar alguns minutos por causa do `ultralytics`/`opencv`/`mediapipe`).
3. Quando o serviço estiver **Live**, copie a URL pública (ex.: `https://visionsaas-backend.onrender.com`).
4. Vá em **Environment** do serviço e preencha as variáveis marcadas `sync: false` no blueprint (elas não vêm com valor, por segurança):

   | Variável | Valor |
   |---|---|
   | `SUPER_ADMIN_EMAIL` | seu e-mail de dono da plataforma |
   | `SUPER_ADMIN_PASSWORD` | uma senha forte (troque depois pelo painel) |
   | `FRONTEND_URL` | preencha **depois** do passo 2 (URL da Vercel) |
   | `BACKEND_URL` | a própria URL do Render (passo 3 acima) |
   | `CORS_ORIGINS` | deixe em branco (usa `FRONTEND_URL` automaticamente) |
   | `STRIPE_PUBLISHABLE_KEY` | ver passo 4 |
   | `STRIPE_SECRET_KEY` | ver passo 4 |
   | `STRIPE_WEBHOOK_SECRET` | ver passo 4 |
   | `STRIPE_PRICE_ID_UNICO` | ver passo 4 |
   | `RESEND_API_KEY` | ver passo 5 |
   | `EMAIL_FROM` | ver passo 5 |

   > ⚠️ **Câmeras reais e visão computacional (YOLOv8) pedem bastante CPU/RAM.**
   > O plano `free` do Render sobe a API/painel/billing sem problema, mas para
   > processar streams de câmera de verdade em produção, migre o serviço para
   > um plano pago (mais RAM/CPU, sem "sleep" por inatividade).

5. Cada vez que você mudar uma env var, o Render reinicia o serviço sozinho — não precisa redeploy manual.

---

## 2. Frontend na Vercel

O repo já tem `frontend/vercel.json` (rewrite de SPA, evita 404 ao dar F5 numa rota como `/dashboard`).

1. Vercel Dashboard → **Add New** → **Project** → importe o mesmo repositório.
2. Em **Root Directory**, selecione `frontend` (o projeto Vite não está na raiz do repo).
3. Vercel detecta Vite automaticamente (build `npm run build`, output `dist`) — não precisa mexer.
4. Em **Environment Variables**, adicione:

   | Variável | Valor |
   |---|---|
   | `VITE_API_URL` | a URL do backend no Render (passo 1.3) |
   | `VITE_STRIPE_PUBLISHABLE_KEY` | a mesma `pk_...` do passo 4 (não é usada hoje, é só documentação para uso futuro) |

5. **Deploy**. Copie a URL final (ex.: `https://visionsaas.vercel.app`).
6. Volte no Render (passo 1.4) e preencha `FRONTEND_URL` com essa URL — sem isso, o CORS bloqueia o frontend e os links do Stripe Checkout/Portal voltam para o lugar errado.

---

## 3. Domínio próprio (opcional)

Se for usar um domínio (ex.: `app.suaempresa.com`):
- Vercel: **Settings → Domains** → adicione o domínio e siga as instruções de DNS (CNAME).
- Render: **Settings → Custom Domain** no serviço backend, se quiser `api.suaempresa.com` em vez da URL `*.onrender.com`.
- Depois de trocar, **atualize `FRONTEND_URL`/`BACKEND_URL`** nas duas plataformas para os domínios finais.

---

## 4. Stripe (chaves de produção + webhook)

1. No [Dashboard da Stripe](https://dashboard.stripe.com), **saia do modo Teste** (toggle no canto — vá para **Live**).
2. **Developers → API keys**: copie `pk_live_...` e `sk_live_...`.
3. **Product catalog → Add product**: crie **"Plano Completo"**, preço recorrente, mensal, **R$ 0,10**, moeda BRL. Copie o `price_...` gerado.
4. **Developers → Webhooks → Add endpoint**:
   - URL: `https://SEU-BACKEND-NO-RENDER/api/webhooks/stripe`
   - Eventos: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copie o **Signing secret** (`whsec_...`).
5. Volte no Render (passo 1.4) e preencha:
   - `STRIPE_PUBLISHABLE_KEY` = `pk_live_...`
   - `STRIPE_SECRET_KEY` = `sk_live_...`
   - `STRIPE_WEBHOOK_SECRET` = `whsec_...` (do passo 4.4)
   - `STRIPE_PRICE_ID_UNICO` = `price_...` (do passo 4.3)
6. Na Vercel (passo 2.4), atualize `VITE_STRIPE_PUBLISHABLE_KEY` para a mesma `pk_live_...`.

> Em dev/teste, use as chaves `pk_test_.../sk_test_...` normalmente — não precisa repetir esses passos, só troque para `_live_` quando for cobrar de verdade.

---

## 5. E-mails transacionais (Resend)

1. [resend.com](https://resend.com) → crie a conta → **API Keys → Create API Key**. Copie o `re_...`.
2. **Domains → Add Domain**: adicione seu domínio e configure os registros DNS (SPF/DKIM) indicados — sem isso, você só consegue enviar para o seu próprio e-mail de teste.
3. Depois do domínio verificado, defina `EMAIL_FROM` (Render) como algo como `VisionSaaS <contato@seudominio.com>`.
4. Preencha `RESEND_API_KEY` no Render (passo 1.4). Sem essa chave, os e-mails de boas-vindas e confirmação de assinatura só são logados, não quebram o sistema.

---

## 6. Checklist final (smoke test em produção)

- [ ] Abrir a URL da Vercel → landing page carrega.
- [ ] `/registrar` → criar uma empresa de teste → cai no `/dashboard` já logado, `status_assinatura = trial`.
- [ ] Cadastrar uma câmera em `/cameras`.
- [ ] `/assinatura` → **Assinar Agora** → completar o checkout (com um [cartão de teste](https://docs.stripe.com/testing) se ainda estiver em modo Teste) → confirmar que o status vira **Ativa** sozinho (webhook) em alguns segundos.
- [ ] Conferir se chegou o e-mail de boas-vindas e o de assinatura confirmada.
- [ ] Logar como SUPER_ADMIN (`SUPER_ADMIN_EMAIL`/`SUPER_ADMIN_PASSWORD`) em `/login` → `/admin` → ver a empresa de teste na lista, com o total de câmeras certo → testar **Suspender** e confirmar que o painel da empresa bloqueia (403 → redireciona pra `/assinatura`).

---

## Referência rápida de variáveis

**Backend (Render)** — ver `backend/.env.example` para o detalhe de cada uma:
`DATABASE_URL`, `SECRET_KEY`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `TRIAL_DIAS`,
`FRONTEND_URL`, `BACKEND_URL`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_UNICO`, `RESEND_API_KEY`, `EMAIL_FROM`,
`CORS_ORIGINS` (opcional).

**Frontend (Vercel)** — ver `frontend/.env.example`:
`VITE_API_URL`, `VITE_STRIPE_PUBLISHABLE_KEY`.
