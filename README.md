# VisionSaaS — Plataforma de Inteligência Operacional por Câmeras

SaaS de visão computacional (YOLOv8 + ByteTrack) para monitoramento de atendimento,
ocupação e postura por câmera, com anonimização automática (LGPD), RBAC
(SUPER_ADMIN / CLIENTE) e exportação de relatórios em PDF/Excel.

```
meu-sistema-ia/
├── backend/       # FastAPI + SQLite + visão computacional (ver backend/README.md)
├── frontend/      # React + Vite + Tailwind (ver frontend/README.md)
├── run_app.py     # sobe tudo de uma vez (setup + backend + frontend + browser)
├── start.bat      # wrapper para Windows
└── start.sh       # wrapper para Linux/macOS
```

## Início rápido

Pré-requisitos: **Python 3.10+** e **Node.js 18+** instalados e no PATH.

```powershell
python run_app.py
```

(ou `start.bat` no Windows / `./start.sh` no Linux/macOS — ambos só chamam `run_app.py`)

Isso vai, na primeira vez: criar o venv do backend, instalar as dependências Python
(com o PyTorch CPU-only, mais leve) e as do Node, popular o banco com dados de
teste, subir o backend na porta **8000** e o frontend na porta **3000**, e abrir o
navegador automaticamente. Nas próximas vezes, os passos de instalação são
verificados rapidamente e pulados se já estiverem satisfeitos.

Flags úteis: `--no-install` (pula pip/npm install), `--no-seed` (não popula dados
de teste), `--no-browser` (não abre o navegador). Pressione `Ctrl+C` no terminal
para encerrar backend e frontend juntos.

## Dados de teste (`backend/seed.py`)

Rodado automaticamente pelo `run_app.py` (idempotente — seguro rodar de novo a
qualquer momento, nunca duplica registros):

| Conta | Email | Senha | Papel |
|---|---|---|---|
| Admin do sistema | `admin@sistema.com` | `admin123` | SUPER_ADMIN |
| Padaria Silva | `gerente@padaria.com` | `cliente123` | CLIENTE |
| Escritório Santos | `gerente@escritorio.com` | `cliente123` | CLIENTE |

A **Padaria Silva** já vem com uma câmera pré-configurada ("Balcão Principal
(Webcam)") apontando para a webcam local do computador (índice `0`), perfil
`balcao_loja` — pronta para o teste prático abaixo. Nenhuma zona é criada
automaticamente: desenhar as zonas faz parte do teste.

## Teste prático com a webcam

1. **Login como Admin** — acesse http://localhost:3000/login com
   `admin@sistema.com` / `admin123`.
2. No painel Master Admin, escolha a aba **"Padaria Silva"** na lista de
   clientes à esquerda.
3. Vá em **"Câmeras & Zonas"**, clique em **"Zonas"** na câmera "Balcão
   Principal (Webcam)" e desenhe (clicando sobre a imagem da webcam):
   - **Zona Atendente** no lado **esquerdo** da tela;
   - **Zona Cliente** no lado **direito** da tela.

   Clique em "Finalizar zona" após posicionar pelo menos 3 pontos de cada uma,
   depois em **"Salvar Zonas"**.
4. Fique parado do lado **esquerdo** da webcam (simulando o atendente) e peça
   para alguém — ou você mesmo, revezando — ficar do lado **direito** por mais
   de **15 segundos** (simulando o cliente sendo atendido); depois saia da
   zona da direita. O overlay do vídeo mostra **"ATENDIMENTO EM ANDAMENTO"**
   assim que os 15s são atingidos.
5. Veja o contador **"Clientes Atendidos Hoje"** incrementar em tempo real no
   Dashboard — pela própria aba do admin, ou fazendo login como
   `gerente@padaria.com` / `cliente123` para ver exatamente a visão do
   lojista.
6. Na aba **"Relatórios"**, clique em **"Baixar Relatório PDF"** (ou
   "Exportar Planilha Excel") para conferir o atendimento recém-gerado no
   relatório exportado.

> Sem webcam disponível? Troque a URL da câmera (em "Câmeras & Zonas" →
> Editar) por uma URL RTSP real, ou deixe `0` mesmo assim — o sistema
> continua funcionando normalmente, só não vai detectar pessoas sem uma
> fonte de vídeo de verdade.

## Mais detalhes

- Arquitetura de visão computacional, RBAC e API: `backend/README.md`.
- Estrutura do frontend e componentes: `frontend/README.md`.
