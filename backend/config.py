"""
Configurações globais da aplicação.

Lidas de variáveis de ambiente (arquivo .env na raiz do backend) com valores
padrão seguros o suficiente para desenvolvimento local. Em produção, defina
SECRET_KEY e SUPER_ADMIN_PASSWORD via variáveis de ambiente reais.
"""
import os

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

# --- SaaS / assinaturas ---
# Duração do período de teste gratuito concedido a toda empresa nova (cadastro
# público em /api/auth/signup e também às empresas herdadas na migração do
# esquema antigo — ver database._migrar_para_multi_tenant).
TRIAL_DIAS = int(os.getenv("TRIAL_DIAS", "14"))

# URL pública do frontend, usada para montar as URLs de retorno do Stripe Checkout
# e do Customer Portal (success_url/cancel_url/return_url) e como origem permitida
# de CORS por padrão (ver CORS_ORIGINS, abaixo).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

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
YOLO_TRACKER = os.getenv("YOLO_TRACKER", "bytetrack.yaml")

STREAM_JPEG_QUALITY = int(os.getenv("STREAM_JPEG_QUALITY", "80"))
STREAM_TARGET_FPS = int(os.getenv("STREAM_TARGET_FPS", "15"))
BLUR_KERNEL = int(os.getenv("BLUR_KERNEL", "51"))  # precisa ser ímpar

# --- Regras de negócio por perfil de câmera (ajustáveis por variável de ambiente) ---

# Balcão/Loja: tempo mínimo de presença conjunta (atendente + cliente) para validar
# um "Atendimento Em Andamento". Abaixo disso, o evento ainda é registrado ao sair,
# porém marcado como não concluído (abandono/passagem rápida).
ATENDIMENTO_MIN_SEGUNDOS = float(os.getenv("ATENDIMENTO_MIN_SEGUNDOS", "15"))

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

# --- CORS ---
# Em produção, a origem confiável por padrão é o próprio FRONTEND_URL (evita
# esquecer de travar isso ao publicar). Defina CORS_ORIGINS explicitamente
# (separado por vírgula, ou "*") só se precisar liberar mais de uma origem ou
# rodar sem restrição em dev.
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",")] if _CORS_ORIGINS_RAW else [FRONTEND_URL]
