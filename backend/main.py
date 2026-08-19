"""
Ponto de entrada da aplicação FastAPI.

Executar com:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import BACKEND_URL, CORS_ORIGINS
from database import init_db, seed_super_admin
from routes import router
from vision import camera_manager

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


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_super_admin()
    print(f"[stripe] Configure o webhook da assinatura para: {BACKEND_URL}/api/webhooks/stripe")
    print(f"[cors] Origens permitidas: {_origens_permitidas}")


@app.on_event("shutdown")
def on_shutdown() -> None:
    camera_manager.stop_all()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "camera-intelligence-saas"}


app.include_router(router)
