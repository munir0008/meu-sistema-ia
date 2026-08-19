# Plataforma SaaS de Inteligência Operacional por Câmeras — Backend

Backend em FastAPI para detecção/rastreamento de pessoas via câmeras (RTSP/ONVIF ou webcam),
com anonimização automática (blur, LGPD) e métricas de atendimento/ocupação por zona,
em um banco SQLite multi-cliente.

## Estrutura

```
backend/
├── main.py        # App FastAPI, CORS, startup/shutdown
├── database.py     # Engine/Session SQLAlchemy (SQLite)
├── models.py        # Tabelas ORM: clientes, cameras, zonas, metricas_*
├── schemas.py        # Contratos Pydantic de entrada/saída
├── auth.py            # Hash de senha (bcrypt) + JWT
├── vision.py            # CameraStream, VideoProcessor, CameraManager (YOLOv8 + blur + métricas)
├── routes.py              # Todos os endpoints da API
├── requirements.txt
└── .env.example
```

## 1. Pré-requisito: Python

Este projeto precisa de **Python 3.10+** instalado. Baixe em https://www.python.org/downloads/
(marque "Add python.exe to PATH" durante a instalação) ou instale via `winget install Python.Python.3.11`.

## 2. Instalação

```powershell
cd backend
python -m venv venv
venv\Scripts\activate

# Recomendado no Windows sem GPU: instalar o PyTorch CPU-only primeiro (bem mais leve)
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt

copy .env.example .env
```

O primeiro uso do YOLOv8 baixa automaticamente o peso `yolov8n.pt` (~6 MB) na primeira execução.

## 3. Executar o servidor

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa (Swagger): http://localhost:8000/docs

## 4. RBAC (SUPER_ADMIN x CLIENTE)

Login único para os dois papéis — `POST /api/auth/login` devolve um JWT com os claims
`cliente_id` e `role`, e a mesma informação "aberta" no corpo da resposta:

```json
{ "access_token": "...", "token_type": "bearer", "role": "SUPER_ADMIN", "cliente_id": 1, "nome_empresa": "..." }
```

No primeiro startup, se não existir nenhuma conta `SUPER_ADMIN`, o backend cria uma
automaticamente com `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD` (ver `.env.example`) —
**troque a senha padrão** assim que possível (é uma conta normal depois de criada, dá
para editar por `PUT /api/admin/clientes/{id}` como qualquer outra).

| Ação | SUPER_ADMIN | CLIENTE |
|---|---|---|
| `GET/POST/PUT/DELETE /api/admin/clientes` | ✅ (qualquer cliente) | ❌ 403 |
| `GET /api/admin/cameras` | ✅ (todas, ou `?cliente_id=` para filtrar) | ✅ (somente as próprias) |
| `POST/PUT/DELETE /api/admin/cameras` | ✅ (qualquer cliente) | ❌ 403 |
| `GET/POST /api/admin/cameras/{id}/zonas` | ✅ (qualquer câmera) | ❌ 403 |
| `GET /api/video_feed/{id}` | ✅ (qualquer câmera) | ✅ (somente as próprias) |
| `GET /api/metrics/dashboard/{cliente_id}` | ✅ (qualquer cliente) | ✅ (somente o próprio `cliente_id`) |

Cada rota protegida depende de `get_current_cliente` (valida o JWT) e, quando restrita,
de `require_roles(...)` (valida o papel) em `auth.py` — é aí que fica a validação
"middleware" de token + permissão citada no requisito, aplicada por rota via
`Depends(...)` do FastAPI.

## 5. Fluxo de uso da API

1. **Login como SUPER_ADMIN** (bootstrap, credenciais do `.env`):

   ```
   POST /api/auth/login
   Body: {"email": "admin@visionsaas.com", "senha": "admin123"}
   ```

2. **Criar um cliente (role CLIENTE)** usando o JWT do SUPER_ADMIN:

   ```
   POST /api/admin/clientes
   Header: Authorization: Bearer <token do SUPER_ADMIN>
   Body: {"nome_empresa": "Loja Exemplo", "email": "dono@loja.com", "senha": "senha123"}
   ```

   (`role` é opcional no payload — o padrão já é `CLIENTE`.)

3. **Cadastrar uma câmera para esse cliente** (ainda como SUPER_ADMIN):

   ```
   POST /api/admin/cameras
   Body: {"cliente_id": 2, "nome_camera": "Balcão Principal",
          "rtsp_url": "0", "perfil_ativo": "balcao_loja"}
   ```

   Use `"rtsp_url": "0"` para testar com a webcam local, ou uma URL real,
   ex.: `"rtsp://usuario:senha@192.168.0.10:554/stream1"`.

4. **Desenhar e salvar zonas** (coordenadas normalizadas 0.0–1.0, vindas do frontend;
   somente SUPER_ADMIN):

   ```
   POST /api/admin/cameras/1/zonas
   Body: {
     "zonas": [
       {"tipo_zona": "atendente", "coordenadas": [[0.1,0.1],[0.4,0.1],[0.4,0.5],[0.1,0.5]]},
       {"tipo_zona": "cliente",   "coordenadas": [[0.5,0.1],[0.9,0.1],[0.9,0.5],[0.5,0.5]]}
     ]
   }
   ```

5. **Login como o cliente da loja** e uso do próprio dashboard/streaming:

   ```
   POST /api/auth/login   Body: {"email": "dono@loja.com", "senha": "senha123"}
   GET /api/video_feed/1              Header: Authorization: Bearer <token do cliente>
   GET /api/metrics/dashboard/2       Header: Authorization: Bearer <token do cliente>
   ```

## LGPD / Privacidade

- Nenhum frame, recorte facial ou embedding biométrico é gravado em disco/banco.
- Todo frame é anonimizado (Gaussian Blur nas pessoas detectadas + camada extra de
  detecção facial via MediaPipe) **antes** de ser codificado/transmitido.
- Apenas contadores e durações agregadas são persistidos (`metricas_atendimento`,
  `metricas_ocupacao`).

## Algoritmo de análise por perfil de câmera (`vision.py`)

Cada câmera roda em sua própria thread de processamento dedicada (ver docstring no
topo de `vision.py`), independente do número de pessoas assistindo o stream, e com
sua própria instância de modelo YOLO — necessário porque `model.track(persist=True)`
mantém estado de rastreamento por instância; compartilhar um modelo entre câmeras
diferentes corromperia a continuidade dos IDs do ByteTrack de uma câmera com a de
outra rodando em paralelo.

**Balcão/Loja** (`VideoProcessor._atualizar_atendimento_balcao`): monitora as zonas
'atendente' e 'cliente' simultaneamente. Quando há um ID em cada zona ao mesmo tempo,
inicia um cronômetro para aquele cliente; se a presença conjunta continuar por
`ATENDIMENTO_MIN_SEGUNDOS` (padrão 15s), o par é validado como "Atendimento Em
Andamento" (sinalizado no overlay do vídeo). Quando o cliente sai da zona, o
cronômetro é encerrado e uma linha é gravada em `metricas_atendimento` com a duração
exata — `concluido=True` somente se chegou a ser validado, senão fica registrado como
abandono. Anti-duplicação: o ID do cliente fica em cooldown por
`CLIENTE_COOLDOWN_SEGUNDOS` (padrão 30s) após sair, evitando recontagem por flicker
de detecção/oclusão breve.

**Escritório** (`_atualizar_escritorio`): mede atividade real (não só presença) na
zona 'trabalho' — uma pessoa parada conta como inatividade tanto quanto uma zona
vazia. Ao cruzar `ESCRITORIO_INATIVIDADE_SEGUNDOS` (padrão 300s) sem deslocamento
perceptível, registra um evento em `metricas_ocupacao` (uma vez por episódio de
inatividade; reseta quando a atividade retoma).

**Estoque** (`_atualizar_estoque`): mede movimentação contínua no espaço monitorado
e identifica áreas de estagnação usando um grid (`ESTOQUE_GRID_COLUNAS` x
`ESTOQUE_GRID_LINHAS`, padrão 8x6) — quando alguém permanece parado na mesma célula
por `ESTOQUE_ESTAGNACAO_SEGUNDOS` (padrão 120s), grava um evento. O grid em si (onde
ficam as áreas de estagnação) é mantido só em memória — persistir um mapa espacial
exigiria uma tabela nova, fora do escopo do schema atual.

O que conta como "movimento perceptível" é configurável via
`MOVIMENTO_MINIMO_NORMALIZADO` (fração da diagonal do frame entre duas amostras).

Essas regras são um ponto de partida (MVP) documentado em comentários no código —
ajuste os limiares em `.env` ou a lógica dos métodos citados conforme a regra de
negócio real de cada perfil.
