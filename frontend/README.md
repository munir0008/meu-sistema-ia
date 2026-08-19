# VisionSaaS — Frontend

Dashboard React (Vite + Tailwind CSS v4, tema escuro) para a Plataforma SaaS de
Inteligência Operacional por Câmeras. Consome a API FastAPI do diretório `../backend`.

## Stack

- React 19 + Vite
- Tailwind CSS v4 (via `@tailwindcss/vite`, sem `tailwind.config.js` — tokens em `src/index.css`)
- `react-router-dom`, `axios`, `recharts`, `lucide-react`

## Estrutura

```
src/
├── api/          # axios (client.js com interceptor JWT) + funções por recurso
├── components/
│   ├── admin/    # painel Master Admin (clientes, chave admin)
│   ├── auth/     # ProtectedRoute
│   ├── cameras/  # player MJPEG, formulário, editor de zonas
│   ├── charts/   # gráficos Recharts
│   ├── layout/   # Sidebar, Topbar, DashboardLayout
│   └── ui/       # Button, Input, Select, Card, Modal, Badge...
├── context/      # AuthContext (JWT do cliente), AdminContext (X-Admin-Key)
├── pages/        # Login, Dashboard, Câmeras ao Vivo, Configurações, Relatórios, Admin
└── utils/        # decodificação de JWT, formatação
```

## Executar

```bash
npm install
cp .env.example .env   # ajuste VITE_API_URL se o backend não estiver em localhost:8000
npm run dev
```

Acesse http://localhost:3000. O backend precisa estar rodando em paralelo (ver `../backend/README.md`).

> Para subir backend + frontend juntos com um único comando (venv, `npm install`, seed de dados
> de teste e abertura automática do navegador), use `python run_app.py` na raiz do projeto —
> ver `../README.md`.

## Fluxo de autenticação

- **Lojista/cliente**: faz login em `/login` (email+senha) → JWT salvo em `localStorage` →
  todas as chamadas autenticadas passam pelo axios de `src/api/client.js`, que injeta
  `Authorization: Bearer <token>` automaticamente e desloga em qualquer `401`.
- **Master Admin**: `/admin` tem um gate próprio, independente do login do lojista — pede a
  `X-Admin-Key` (definida no `.env` do backend) e a usa em todas as chamadas de
  `/api/admin/clientes`.

## Streaming de vídeo (MJPEG)

`GET /api/video_feed/{camera_id}` no backend exige JWT — mas uma tag `<img>` não consegue
enviar headers customizados. Por isso o token também é aceito via query string
(`?token=...`) **somente nesse endpoint** (ajuste feito em `backend/auth.py` /
`get_current_cliente_stream`, mantendo os demais endpoints estritos por header). As caixas
delimitadoras de pessoas e os polígonos de zona já vêm desenhados no vídeo pelo backend
(`vision.py`), com blur automático de anonimização — o frontend não precisa desenhar overlay.

## Limitações conhecidas (herdadas da API atual)

- O dashboard/relatório traz apenas o dia corrente — não há endpoint de intervalo de datas.
- A distribuição "por zona" no dashboard é aproximada por câmera (`por_camera`), pois o
  backend não agrega métricas por tipo de zona, apenas por câmera.
- No painel Master Admin, a coluna "Câmeras por cliente" fica indisponível: não existe hoje
  um endpoint admin que liste câmeras de qualquer cliente (o `GET /api/admin/cameras` é
  escopado ao cliente do JWT). Adicionar isso exigiria uma nova rota protegida por
  `X-Admin-Key` no backend.
