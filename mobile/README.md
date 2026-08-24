# App Mobile — Inteligência de Loja (Expo)

App mobile (iOS/Android) do mesmo produto do painel web (`../frontend`), consumindo a
API Python/FastAPI já existente em `../backend` — nenhuma rota ou tabela do backend foi
alterada para este app existir. Stack: **Expo (Managed Workflow) + TypeScript + Expo
Router + NativeWind (Tailwind) + Axios**.

## O que tem hoje

- **Login** (`src/app/login.tsx`) — autentica em `POST /api/auth/login` (o mesmo JWT do
  painel web) e guarda a sessão no `AsyncStorage`, pra continuar logado entre aberturas
  do app.
- **Dashboard** (`src/app/(tabs)/dashboard.tsx`) — consome
  `GET /api/metrics/dashboard/{empresa_id}` e mostra os cards de atendimento de
  balcão/caixa: Clientes Atendidos, Fila, Desistências e Ociosidade. Toggle de período
  (Hoje / 7 dias / 30 dias), igual ao painel web.
- **Câmeras** (`src/app/(tabs)/cameras.tsx`) — lista as câmeras da empresa
  (`GET /api/admin/cameras`) e exibe o stream ao vivo de cada uma (mesmo endpoint MJPEG
  do painel web, `GET /api/video_feed/{id}`).
- **Assinatura** (`src/app/(tabs)/assinatura.tsx`) — consome `GET /api/empresa/minha` e
  mostra Plano/Status/Próxima cobrança em modo **somente leitura**. De propósito
  **sem nenhum botão/link de checkout ou de gestão de assinatura** — só um aviso pra
  usar o painel web pra isso (ver docstring no topo do arquivo: é uma exigência das
  diretrizes da App Store/Google Play sobre compras digitais fora do sistema de compra
  da própria loja, não uma limitação técnica).

Contas **SUPER_ADMIN** (sem empresa associada) conseguem logar, mas o Dashboard mobile
mostra um aviso — esse app é feito pra quem opera UMA loja (conta ADMIN/USER de uma
empresa), não pra administração da plataforma (isso continua sendo função do painel
web).

## Rodando localmente

### 1. Instalar dependências

```bash
cd mobile
npm install
```

### 2. Apontar para o backend

Copie `.env.example` para `.env` e ajuste a URL:

```bash
cp .env.example .env
```

- **Testando no seu iPhone/Android físico com o backend rodando na SUA máquina**: use o
  IP da sua máquina *na rede local* (não `localhost` — no celular isso aponta pro
  próprio celular). No Windows, pegue o IP com `ipconfig` (campo "Endereço IPv4" da
  rede Wi-Fi) e edite `.env`:

  ```
  EXPO_PUBLIC_API_URL=http://192.168.0.10:8000
  ```

  Seu celular e seu computador precisam estar na **mesma rede Wi-Fi**, e o backend
  local precisa estar rodando (`cd ../backend && uvicorn main:app --host 0.0.0.0 --port 8000`
  — o `--host 0.0.0.0` é obrigatório pra aceitar conexão de outro aparelho, não só do
  próprio PC).

- **Testando contra produção (Render)**: não precisa mexer em nada — sem um `.env`, o
  app já usa a URL do backend em produção como padrão (ver `src/api/client.ts`). Só
  crie o `.env` mesmo se quiser apontar pra outro lugar (ex.: seu backend local).

### 3. Iniciar o app

```bash
npx expo start
```

Isso abre o **Metro Bundler** no terminal com um QR code.

## Testando no iPhone com o Expo Go (grátis, sem Mac/Xcode)

1. Instale o app **Expo Go** na App Store (gratuito).
2. Com `npx expo start` rodando (passo acima), abra a câmera do iPhone e aponte pro QR
   code que aparece no terminal — o iOS reconhece automaticamente e oferece abrir no
   Expo Go.
3. O app carrega direto no seu iPhone. Qualquer alteração salva no código atualiza a
   tela na hora (Fast Refresh), sem precisar reinstalar nada.

No Android é o mesmo fluxo: abra o Expo Go, toque em "Scan QR code" e aponte pro QR do
terminal.

> Se o QR code não conectar: confirme que o celular está na mesma rede Wi-Fi do
> computador rodando `expo start`. Redes de convidado ("guest") costumas isolar os
> aparelhos entre si e o QR nunca conecta — nesse caso, tente `npx expo start --tunnel`
> (mais lento, mas passa por fora da rede local).

## Estrutura de pastas

```
mobile/
  src/
    app/                  # Rotas (Expo Router — cada arquivo = uma tela)
      _layout.tsx           # Auth gate (Stack.Protected): login vs. (tabs)
      login.tsx
      (tabs)/
        _layout.tsx          # Barra de abas: Dashboard / Câmeras / Assinatura
        dashboard.tsx
        cameras.tsx
        assinatura.tsx        # Read-only — ver seção "O que tem hoje" acima
    api/                  # Chamadas HTTP (axios) pra API do backend
      client.ts             # Instância do axios + EXPO_PUBLIC_API_URL + token
      auth.ts
      dashboard.ts
      cameras.ts
      empresa.ts
    context/
      AuthContext.tsx        # Sessão (token/role/empresa) + AsyncStorage
    components/
      KpiCard.tsx
      CameraStreamView.tsx   # Stream MJPEG via WebView (ver comentário no arquivo)
    types/
      api.ts                 # Tipos espelhando os schemas Pydantic do backend
    utils/
      format.ts               # Rótulos/cores de status (espelha frontend/src/utils/format.js)
  tailwind.config.js / babel.config.js / metro.config.js   # NativeWind
  .env.example
```

## Notas técnicas

- **Por que WebView pro vídeo, não `<Image>`**: o stream de câmera do backend é MJPEG
  (`multipart/x-mixed-replace`) — o mesmo formato que um `<img>` de navegador exibe
  nativamente. O componente `<Image>` do React Native (iOS/Android) não decodifica esse
  formato contínuo, só uma imagem estática por resposta. Por isso
  `CameraStreamView.tsx` usa `react-native-webview` com uma página HTML mínima
  (`<img src="...">` dentro dela) — o motor de navegador embutido na WebView entende
  MJPEG do mesmo jeito que o Chrome/Safari do painel web.
- **Autenticação do stream de vídeo**: como não dá pra anexar um header
  `Authorization` numa URL de imagem/WebView, o token vai na própria query string
  (`?token=...`) — o backend já aceita isso desde que o painel web foi construído (ver
  `auth.get_current_usuario_stream` no backend), então nenhuma mudança foi necessária
  ali.
- **Nenhuma rota/tabela do backend foi alterada** para este app existir — ele consome
  exatamente a mesma API que o painel web já usa.

## Publicando (fora do escopo deste setup inicial)

Rodar via Expo Go cobre desenvolvimento/teste. Para distribuir de verdade (TestFlight /
Play Store, ou usar algum módulo nativo fora do Expo Go), o próximo passo é
[EAS Build](https://docs.expo.dev/build/introduction/) — não configurado ainda neste
projeto.
