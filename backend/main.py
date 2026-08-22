"""
Ponto de entrada da aplicação FastAPI.

Executar com:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import BACKEND_URL, CORS_ORIGINS, YOLO_MODEL_PATH
from database import init_db, seed_super_admin
from routes import router
from vision import camera_manager

# Sem isto, os `logger.info(...)` espalhados pelo backend (payments.py,
# routes.py, emails.py) ficam mudos: o root logger do Python nasce em WARNING
# e sem handler, e o uvicorn não configura isso pra gente — só os próprios
# loggers "uvicorn.*". Nível INFO aqui é o que faz os logs de diagnóstico do
# fluxo de pagamento (Stripe) aparecerem no dashboard do Render.
#
# `%(process)d` no formato é deliberado: `camera_manager` (vision.py) é um
# registry EM MEMÓRIA de UM processo — se o serviço no Render rodar mais de
# uma instância, o WebSocket de ingest de uma câmera "browser" (que fica preso
# na instância que aceitou a conexão) e as requisições HTTP de leitura
# (/video_feed, /admin/cameras) podem cair em instâncias DIFERENTES, cada uma
# com seu próprio VideoProcessor isolado pra mesma câmera — a que só recebe
# nunca vê frame nenhum. Com o PID no log dá pra confirmar isso na hora: se
# "camera_ingest conectado" e "primeiro frame entregue" aparecerem com PIDs
# diferentes para a mesma câmera, é exatamente isso.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [pid=%(process)d] %(name)s: %(message)s")

app = FastAPI(
    title="Plataforma SaaS de Inteligência Operacional por Câmeras",
    description=(
        "API de detecção/rastreamento de pessoas (YOLOv8 + ByteTrack) com anonimização "
        "automática (LGPD) e métricas de atendimento/ocupação por zona."
    ),
    version="1.0.0",
)

# Origens sempre liberadas, além do que `CORS_ORIGINS`/`FRONTEND_URL` definir via
# variável de ambiente — rede de segurança para o frontend oficial em produção
# nunca ficar bloqueado por um valor de env var ausente/errado na plataforma de
# deploy (foi exatamente o que aconteceu ao publicar: `FRONTEND_URL` configurada
# certinha no Render, mas a origem seguia sendo recusada). Adicione aqui outros
# domínios fixos (ex.: domínio próprio) se/quando existirem.
ORIGENS_SEMPRE_PERMITIDAS = ["https://meu-sistema-ia.vercel.app"]

_origens_permitidas = sorted(set(CORS_ORIGINS) | set(ORIGENS_SEMPRE_PERMITIDAS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sem isso, o navegador recebe o header mas NÃO deixa o JS do frontend lê-lo
    # (Content-Disposition não está na safelist padrão de headers expostos em CORS) —
    # necessário para os downloads de relatório extraírem o nome de arquivo sugerido.
    expose_headers=["Content-Disposition"],
)


def _aquecer_yolo_em_background() -> None:
    """
    Pré-aquece o import do `ultralytics`/torch — medido em produção (Render,
    CPU compartilhada) em ~31s, contra ~4s numa máquina de dev razoável — UMA
    VEZ no boot do processo, em vez de deixar a PRIMEIRA câmera que qualquer
    usuário abrir pagar esse custo inteiro dentro do orçamento de
    CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS do generate_mjpeg (foi exatamente
    isso que causava viewer nunca receber frame nenhum e a tela ficar preta:
    o modelo ainda estava carregando quando o timeout do streaming de saída
    estourava). Cada câmera CONTINUA criando sua PRÓPRIA instância de YOLO em
    VideoProcessor._carregar_modelo — necessário pra não misturar estado de
    tracking entre câmeras (ver vision.py) — mas o import pesado do pacote
    Python já estará "quente" (cacheado por sys.modules) quando isso
    acontecer, então cada instância por câmera fica bem mais rápida depois
    deste warmup. Roda em thread própria pra não atrasar o healthcheck do
    Render (`GET /`) nem o restante do startup; falha aqui nunca derruba o
    app — a primeira câmera real simplesmente paga o custo cheio de novo.
    """
    inicio = time.monotonic()
    logger_warmup = logging.getLogger("main")
    try:
        from ultralytics import YOLO

        YOLO(YOLO_MODEL_PATH)  # instância descartada — só para pagar o custo de import/inicialização
        logger_warmup.info("Aquecimento do YOLO concluído em %.1fs.", time.monotonic() - inicio)
    except Exception:
        logger_warmup.exception("Aquecimento do YOLO falhou (não bloqueia o app — câmeras carregam o modelo normalmente sob demanda).")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_super_admin()
    print(f"[stripe] Configure o webhook da assinatura para: {BACKEND_URL}/api/webhooks/stripe")
    print(f"[cors] Origens permitidas: {_origens_permitidas}")
    threading.Thread(target=_aquecer_yolo_em_background, daemon=True).start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    camera_manager.stop_all()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "camera-intelligence-saas"}


app.include_router(router)
