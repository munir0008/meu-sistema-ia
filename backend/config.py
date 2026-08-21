"""
Configurações globais da aplicação.

Lidas de variáveis de ambiente (arquivo .env na raiz do backend) com valores
padrão seguros o suficiente para desenvolvimento local. Em produção, defina
SECRET_KEY e SUPER_ADMIN_PASSWORD via variáveis de ambiente reais.
"""
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

# --- Banco de dados ---
# Em dev, SQLite local (arquivo). Em produção, aponte DATABASE_URL para um Postgres
# gerenciado (Render/Railway/Neon/...) — o SQLAlchemy já suporta os dois via a mesma
# URL, só muda o schema (sqlite:/// vs postgresql://). Plataformas como Render/Heroku
# injetam a URL com o esquema antigo "postgres://", que o SQLAlchemy 2.x não aceita
# mais — normalizamos aqui para não depender de cada provedor fazer isso certo.
_DATABASE_URL_RAW = os.getenv("DATABASE_URL", "sqlite:///./saas_cameras.db")
DATABASE_URL = (
    _DATABASE_URL_RAW.replace("postgres://", "postgresql://", 1)
    if _DATABASE_URL_RAW.startswith("postgres://")
    else _DATABASE_URL_RAW
)

# --- Autenticação JWT ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-troque-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# --- Bootstrap do SUPER_ADMIN ---
# No primeiro startup, se não existir nenhuma conta com role=SUPER_ADMIN, o backend
# cria uma automaticamente com estas credenciais (ver database.seed_super_admin).
# TROQUE a senha em produção — o login funciona como qualquer conta normal depois disso.
SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "admin@visionsaas.com")
SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "admin123")

# URL pública do frontend, usada para montar as URLs de retorno do Stripe Checkout
# e do Customer Portal (success_url/cancel_url/return_url) e como origem permitida
# de CORS por padrão (ver CORS_ORIGINS, abaixo).
#
# A env var pode estar DEFINIDA porém com um valor inválido (ex.: colada de um
# texto/Markdown como "[https://...](https://...)", ou com aspas/espaços
# sobrando) — mesmo problema já visto com VITE_API_URL na Vercel (ver
# frontend/src/api/client.js). Sem validar, isso vira uma URL quebrada
# passada pro Stripe em `return_url`/`success_url`/`cancel_url`, que a API
# rejeita com "Not a valid URL" — o Customer Portal e o Checkout nunca abrem.
_FRONTEND_URL_FALLBACK_PRODUCAO = "https://meu-sistema-ia.vercel.app"


def _resolver_frontend_url(bruto: str) -> str:
    valor = (bruto or "").strip()
    if not valor:
        return "http://localhost:5173"
    partes = urlparse(valor)
    if partes.scheme in ("http", "https") and partes.netloc:
        return valor.rstrip("/")
    print(
        f"[config] FRONTEND_URL inválida ({valor!r}) — usando fallback de produção "
        f"({_FRONTEND_URL_FALLBACK_PRODUCAO}). Corrija a env var no dashboard do Render."
    )
    return _FRONTEND_URL_FALLBACK_PRODUCAO


FRONTEND_URL = _resolver_frontend_url(os.getenv("FRONTEND_URL", "http://localhost:5173"))

# URL pública do próprio backend (ex.: https://seu-app.onrender.com). Não é usada
# para nenhuma regra de negócio — só para logar, no startup, o endpoint exato que
# você precisa cadastrar como webhook na Stripe (ver main.py).
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# --- Stripe ---
# Chaves de teste em dev (pk_test_.../sk_test_...) e de produção ao publicar
# (pk_live_.../sk_live_...) — preencha no .env. Sem elas, os endpoints de
# pagamento respondem 503 em vez de quebrar o resto da API.
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
# Plano único da plataforma (ver models.PlanoAssinatura.completo): price ID
# (price_...) criado no Dashboard da Stripe para a assinatura mensal recorrente.
STRIPE_PRICE_ID_UNICO = os.getenv("STRIPE_PRICE_ID_UNICO", "")

# --- E-mails transacionais (Resend) ---
# Sem RESEND_API_KEY configurada, os disparos de e-mail (boas-vindas, assinatura
# confirmada) são pulados silenciosamente (logados) — nunca derrubam o cadastro
# nem o processamento do webhook da Stripe.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "VisionSaaS <onboarding@resend.dev>")

# --- Visão computacional ---
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
YOLO_CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.35"))
# Caminho absoluto (não depende do cwd de onde o backend foi iniciado) para o
# tracker customizado deste projeto — ver trackers/bytetrack_custom.yaml: mesmo
# ByteTrack do Ultralytics, só com `track_buffer` maior, para manter o mesmo
# track_id numa oclusão breve (passar atrás de um pilar/outro atendente) em vez
# de reatribuir um ID novo à mesma pessoa. Sobrescreva via env var para usar o
# `bytetrack.yaml` padrão do pacote (ou outro tracker) se preferir.
_TRACKER_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trackers", "bytetrack_custom.yaml")
# `os.getenv` só cai no default quando a env var não existe — se alguém deixar
# `YOLO_TRACKER=` (vazio) no .env, o valor seria a string vazia, não o default
# (mesma pegadinha já documentada para FRONTEND_URL, abaixo). `.strip() or` trata
# vazio/só-espaços como "não configurado".
YOLO_TRACKER = os.getenv("YOLO_TRACKER", "").strip() or _TRACKER_PADRAO

STREAM_JPEG_QUALITY = int(os.getenv("STREAM_JPEG_QUALITY", "80"))
STREAM_TARGET_FPS = int(os.getenv("STREAM_TARGET_FPS", "15"))
BLUR_KERNEL = int(os.getenv("BLUR_KERNEL", "51"))  # precisa ser ímpar

# Por quantos segundos um viewer HTTP (generate_mjpeg) espera pelo PRIMEIRO frame
# antes de desistir e encerrar a resposta. Sem isso, uma câmera cuja fonte nunca
# conecta (ex.: índice de webcam local inexistente no servidor, IP/porta RTSP
# errados) faz o streaming ficar pendurado para sempre — 200 OK, corpo vazio,
# sem nunca disparar o onError da <img> no navegador (tela fica preta sem
# explicação nenhuma). Depois do primeiro frame recebido com sucesso, esse
# timeout deixa de valer (perdas/reconexões subsequentes já são resilientes,
# ver CameraStream._update_loop).
CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS = float(os.getenv("CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS", "20"))

# Por quantos segundos sem receber um frame novo via WebSocket (câmera com
# rtsp_url == "browser", capturada no NAVEGADOR do usuário — ver
# vision.BrowserPushStream e routes.camera_ingest) a fonte é considerada
# desconectada. Cobre o caso da aba do navegador ser fechada sem o WebSocket
# avisar limpo (ex.: queda de rede) — sem isso, o último frame recebido ficaria
# "congelado" sendo servido pra sempre como se a câmera ainda estivesse ao vivo.
CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS = float(os.getenv("CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS", "5"))

# --- Regras de negócio por perfil de câmera (ajustáveis por variável de ambiente) ---

# Balcão/Loja: tempo mínimo de presença conjunta (atendente + cliente) para validar
# um "Atendimento Em Andamento" (dispara SERVICE_STARTED). Default 0 = qualquer
# co-presença confirmada (já passou pelo debounce de zona, ver ZONA_DEBOUNCE_SEGUNDOS
# abaixo) já conta como atendimento imediatamente, mesmo que dure poucos segundos —
# não existe mais um piso de duração mínima para um atendimento ser válido. Suba
# esse valor só se quiser voltar a exigir uma presença conjunta sustentada por mais
# tempo antes de confirmar (abaixo do limiar, o evento ainda é registrado ao sair,
# porém como não concluído/abandono).
ATENDIMENTO_MIN_SEGUNDOS = float(os.getenv("ATENDIMENTO_MIN_SEGUNDOS", "0"))

# Balcão/Loja: por quantos segundos após o cliente sair da zona o ID de rastreamento
# dele fica "em cooldown", ignorado caso reapareça (evita recontagem por flicker de
# detecção/oclusão breve reatribuindo o mesmo ID).
CLIENTE_COOLDOWN_SEGUNDOS = float(os.getenv("CLIENTE_COOLDOWN_SEGUNDOS", "30"))

# Escritório: tempo sem atividade real (pessoa ausente da zona de trabalho OU parada,
# sem deslocamento perceptível) para registrar um evento de inatividade.
ESCRITORIO_INATIVIDADE_SEGUNDOS = float(os.getenv("ESCRITORIO_INATIVIDADE_SEGUNDOS", "300"))

# Deslocamento mínimo do centróide (fração da diagonal do frame, 0.0–1.0) para uma
# pessoa ser considerada "em movimento" entre duas amostras — abaixo disso, "estática".
MOVIMENTO_MINIMO_NORMALIZADO = float(os.getenv("MOVIMENTO_MINIMO_NORMALIZADO", "0.015"))

# Estoque: tempo contínuo de baixa/nenhuma movimentação em uma mesma célula do grid
# de ocupação para marcá-la como área de estagnação.
ESTOQUE_ESTAGNACAO_SEGUNDOS = float(os.getenv("ESTOQUE_ESTAGNACAO_SEGUNDOS", "120"))
ESTOQUE_GRID_COLUNAS = int(os.getenv("ESTOQUE_GRID_COLUNAS", "8"))
ESTOQUE_GRID_LINHAS = int(os.getenv("ESTOQUE_GRID_LINHAS", "6"))

OCUPACAO_AMOSTRA_SEGUNDOS = float(os.getenv("OCUPACAO_AMOSTRA_SEGUNDOS", "30"))

# Balcão/Loja: tempo mínimo que um cliente precisa permanecer na 'Zona Cliente' SEM
# nunca ter havido um atendente presente na 'Zona Atendente' durante a estadia dele
# para contar como "desistência" no Dashboard Analytics (Tópico 1 — Perda de Vendas).
DESISTENCIA_MIN_SEGUNDOS = float(os.getenv("DESISTENCIA_MIN_SEGUNDOS", "180"))

# Balcão/Loja: limiares do alerta "Pico de Fila Sem Atendente" — a 'Zona Cliente'
# atinge PICO_FILA_MIN_PESSOAS (ou mais) pessoas simultâneas enquanto a 'Zona
# Atendente' permanece vazia por PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS contínuos.
PICO_FILA_MIN_PESSOAS = int(os.getenv("PICO_FILA_MIN_PESSOAS", "2"))
PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS = float(os.getenv("PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS", "120"))

# Balcão/Loja: por quantos segundos uma mudança bruta de presença numa zona
# ('Atendente'/'Cliente') precisa se manter estável antes de ser confirmada como
# entrada/saída de verdade (debounce/histerese) — filtra flicker de detecção
# (oscilação de confiança na borda do polígono, oclusão de 1-2 frames) sem
# atrasar demais os eventos de telemetria (ver vision.DebouncePresenca). Com
# ATENDIMENTO_MIN_SEGUNDOS=0 (acima), este é o ÚNICO filtro entre uma detecção
# bruta e um SERVICE_STARTED — mantenha baixo (1-2s) de propósito.
ZONA_DEBOUNCE_SEGUNDOS = float(os.getenv("ZONA_DEBOUNCE_SEGUNDOS", "2.0"))

# Por quantos segundos sem NENHUM frame lido da câmera (queda de conexão) o
# estado de sessões/presença em memória de uma câmera é descartado ao invés de
# mantido pendurado — evita que uma sessão de fila ou presença de atendente que
# estava aberta durante a queda gere uma duração de horas quando a câmera
# finalmente reconectar (ver vision.VideoProcessor._verificar_desconexao_prolongada).
CAMERA_OFFLINE_RESET_SEGUNDOS = float(os.getenv("CAMERA_OFFLINE_RESET_SEGUNDOS", "60"))

# --- CORS ---
# Em produção, a origem confiável por padrão é o próprio FRONTEND_URL (evita
# esquecer de travar isso ao publicar). Defina CORS_ORIGINS explicitamente
# (separado por vírgula, ou "*") só se precisar liberar mais de uma origem ou
# rodar sem restrição em dev.
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",")] if _CORS_ORIGINS_RAW else [FRONTEND_URL]
