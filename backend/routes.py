"""
Endpoints da API, protegidos por JWT + RBAC (SUPER_ADMIN vs ADMIN vs USER).

Fluxo de autenticação:
1. Login em POST /api/auth/login (mesma tela/endpoint para os três papéis)
   emite o JWT de sessão. O autocadastro público em POST /api/auth/signup cria
   a Empresa + o primeiro usuário ADMIN dela, mas SEM login automático — a
   empresa nasce com status `pending_payment` e a resposta só devolve a URL do
   Stripe Checkout (ver routes.signup). O JWT do login carrega `usuario_id`,
   `empresa_id` e `role`; a resposta também devolve esses dados "abertos" para
   o frontend decidir o redirecionamento sem decodificar o token.
2. Toda rota protegida depende de `get_current_usuario` (valida o JWT) e,
   quando a ação é restrita, de `require_roles(...)` (valida o papel).
3. SUPER_ADMIN enxerga e gerencia qualquer empresa/câmera/zona, e nunca é
   bloqueado por assinatura (é uma conta global, sem empresa). ADMIN e USER só
   enxergam a própria empresa e têm CRUD completo das câmeras/zonas dela —
   isolamento garantido no backend (nunca apenas no frontend). Rotas de
   negócio (câmeras, zonas, streaming, métricas, relatórios) exigem também
   `garantir_assinatura_ativa` (bloqueia com 403 se a empresa não estiver com
   assinatura ativa — inclui contas recém-cadastradas em `pending_payment`).
"""
import json
import logging
from collections import defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from typing import Optional

import cv2
import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

import config
import emails
import models
import payments
import reports
import schemas
from auth import (
    _resolve_usuario_from_token,
    criar_token_para_usuario,
    garantir_assinatura_ativa,
    get_current_usuario,
    get_current_usuario_stream,
    hash_password,
    require_roles,
    verify_password,
)
from database import SessionLocal, get_db
import vision
from vision import FONTE_WEBCAM_NAVEGADOR, BrowserPushStream, camera_manager

router = APIRouter()
logger = logging.getLogger("routes")

SUPER_ADMIN = models.RoleUsuario.super_admin
ADMIN = models.RoleUsuario.admin
USER = models.RoleUsuario.user


def _normalizar_email(email: str) -> str:
    """
    E-mail não é case-sensitive (RFC 5321 trata o domínio como tal na prática,
    e usuários digitam com capitalização inconsistente — autocapitalize de
    celular, copiar/colar, etc.). Normaliza para minúsculas + sem espaços nas
    pontas antes de qualquer busca/gravação, para "Nome@Empresa.com" e
    "nome@empresa.com" serem sempre a mesma conta.
    """
    return email.strip().lower()


# ==============================================================================
# AUTENTICAÇÃO
# ==============================================================================
def _token_response(usuario: models.Usuario) -> schemas.Token:
    empresa = usuario.empresa
    return schemas.Token(
        access_token=criar_token_para_usuario(usuario),
        role=usuario.role,
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        nome_empresa=empresa.nome_empresa if empresa else "",
        status_assinatura=empresa.status_assinatura if empresa else None,
    )


@router.post("/api/auth/login", response_model=schemas.Token, tags=["auth"])
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = _normalizar_email(payload.email)
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not usuario or not verify_password(payload.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha inválidos"
        )
    return _token_response(usuario)


@router.post(
    "/api/auth/signup",
    response_model=schemas.SignupResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    """
    Autocadastro público: cria a Empresa (status `pending_payment` — nenhum
    acesso liberado, ver auth.garantir_assinatura_ativa) e seu primeiro
    usuário (ADMIN). SEM login automático: não emitimos JWT aqui de propósito,
    para não existir sessão válida antes do pagamento. A resposta só devolve a
    URL do Stripe Checkout, para onde o frontend redireciona imediatamente —
    a empresa só sai de `pending_payment` quando o webhook confirma o
    pagamento (ver payments.processar_evento_webhook, evento
    checkout.session.completed).

    Se a Stripe não estiver configurada (503), a conta já criada não é
    desfeita: o admin consegue logar normalmente depois (POST /api/auth/login,
    sem checagem de assinatura) e retomar o checkout em /assinatura assim que
    a Stripe for configurada — só as rotas de negócio continuam bloqueadas
    até lá.
    """
    email = _normalizar_email(payload.email)
    existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    empresa = models.Empresa(
        nome_empresa=payload.nome_empresa,
        status_assinatura=models.StatusAssinatura.pending_payment,
    )
    db.add(empresa)
    db.flush()  # garante empresa.id antes de criar o usuário

    usuario = models.Usuario(
        empresa_id=empresa.id,
        nome=payload.nome_admin,
        email=email,
        senha_hash=hash_password(payload.senha),
        role=ADMIN,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    db.refresh(empresa)

    emails.enviar_email_boas_vindas(usuario.email, usuario.nome, empresa)

    try:
        checkout_url = payments.criar_checkout_session(
            db, empresa, models.PlanoAssinatura.completo, usuario.email
        )
    except payments.StripeNaoConfigurado as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return schemas.SignupResponse(empresa_id=empresa.id, checkout_url=checkout_url)


# ==============================================================================
# ADMIN: EMPRESAS (somente SUPER_ADMIN) — backoffice global da plataforma
# ==============================================================================
@router.get(
    "/api/admin/empresas",
    response_model=list[schemas.EmpresaOut],
    tags=["admin-empresas"],
)
def listar_empresas(
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    empresas = db.query(models.Empresa).order_by(models.Empresa.id).all()
    contagem = dict(
        db.query(models.Camera.empresa_id, func.count(models.Camera.id))
        .group_by(models.Camera.empresa_id)
        .all()
    )
    resultado = []
    for empresa in empresas:
        item = schemas.EmpresaOut.model_validate(empresa)
        item.total_cameras = contagem.get(empresa.id, 0)
        resultado.append(item)
    return resultado


@router.put(
    "/api/admin/empresas/{empresa_id}",
    response_model=schemas.EmpresaOut,
    tags=["admin-empresas"],
)
def atualizar_empresa(
    empresa_id: int,
    payload: schemas.EmpresaUpdate,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    """
    Usado pelo painel Master Admin também para "Ativar/Suspender" a conta de
    qualquer empresa em caso de suporte (Ativar -> status_assinatura="active",
    Suspender -> "canceled").
    """
    empresa = db.get(models.Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")

    if payload.nome_empresa is not None:
        empresa.nome_empresa = payload.nome_empresa
    if payload.status_assinatura is not None:
        empresa.status_assinatura = payload.status_assinatura

    db.commit()
    db.refresh(empresa)
    total_cameras = db.query(models.Camera).filter(models.Camera.empresa_id == empresa.id).count()
    item = schemas.EmpresaOut.model_validate(empresa)
    item.total_cameras = total_cameras
    return item


@router.delete(
    "/api/admin/empresas/{empresa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin-empresas"],
)
def remover_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    empresa = db.get(models.Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    for camera in empresa.cameras:
        camera_manager.stop(camera.id)
    db.delete(empresa)  # cascade remove usuarios e cameras (ver models.Empresa)
    db.commit()


# ==============================================================================
# ADMIN: USUÁRIOS SUPER_ADMIN (somente SUPER_ADMIN) — gestão das contas do dono da plataforma
# ==============================================================================
def _garantir_nao_e_ultimo_super_admin(db: Session, usuario: models.Usuario, acao: str) -> None:
    """Bloqueia remover/despromover o único SUPER_ADMIN restante — travaria o sistema."""
    if usuario.role != SUPER_ADMIN:
        return
    outros_admins = (
        db.query(models.Usuario)
        .filter(models.Usuario.role == SUPER_ADMIN, models.Usuario.id != usuario.id)
        .count()
    )
    if outros_admins == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Não é possível {acao}: é o único SUPER_ADMIN do sistema",
        )


@router.get(
    "/api/admin/usuarios",
    response_model=list[schemas.UsuarioOut],
    tags=["admin-usuarios"],
)
def listar_usuarios_super_admin(
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    return db.query(models.Usuario).filter(models.Usuario.role == SUPER_ADMIN).order_by(models.Usuario.id).all()


@router.post(
    "/api/admin/usuarios",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["admin-usuarios"],
)
def criar_usuario_super_admin(
    payload: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    email = _normalizar_email(payload.email)
    existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    usuario = models.Usuario(
        empresa_id=None,
        nome=payload.nome,
        email=email,
        senha_hash=hash_password(payload.senha),
        role=SUPER_ADMIN,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.put(
    "/api/admin/usuarios/{usuario_id}",
    response_model=schemas.UsuarioOut,
    tags=["admin-usuarios"],
)
def atualizar_usuario_super_admin(
    usuario_id: int,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario or usuario.role != SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if payload.nome is not None:
        usuario.nome = payload.nome
    if payload.email is not None:
        usuario.email = _normalizar_email(payload.email)
    if payload.senha is not None:
        usuario.senha_hash = hash_password(payload.senha)

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete(
    "/api/admin/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin-usuarios"],
)
def remover_usuario_super_admin(
    usuario_id: int,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_roles(SUPER_ADMIN)),
):
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario or usuario.role != SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    _garantir_nao_e_ultimo_super_admin(db, usuario, "remover este usuário")
    db.delete(usuario)
    db.commit()


# ==============================================================================
# EMPRESA: EQUIPE (somente ADMIN) — gerenciar contas USER da própria empresa
# ==============================================================================
@router.get(
    "/api/empresa/usuarios",
    response_model=list[schemas.UsuarioOut],
    tags=["empresa-equipe"],
)
def listar_equipe(
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN)),
):
    return (
        db.query(models.Usuario)
        .filter(models.Usuario.empresa_id == atual.empresa_id)
        .order_by(models.Usuario.id)
        .all()
    )


@router.post(
    "/api/empresa/usuarios",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["empresa-equipe"],
)
def criar_membro_equipe(
    payload: schemas.EquipeUsuarioCreate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN)),
):
    email = _normalizar_email(payload.email)
    existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já cadastrado")

    membro = models.Usuario(
        empresa_id=atual.empresa_id,
        nome=payload.nome,
        email=email,
        senha_hash=hash_password(payload.senha),
        role=USER,
    )
    db.add(membro)
    db.commit()
    db.refresh(membro)
    return membro


@router.delete(
    "/api/empresa/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["empresa-equipe"],
)
def remover_membro_equipe(
    usuario_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN)),
):
    membro = db.get(models.Usuario, usuario_id)
    if not membro or membro.empresa_id != atual.empresa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if membro.id == atual.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você não pode remover a própria conta")
    if membro.role == ADMIN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Não é possível remover um ADMIN pela equipe")
    db.delete(membro)
    db.commit()


# ==============================================================================
# EMPRESA: DADOS DA PRÓPRIA EMPRESA (ADMIN/USER) — usado na página "Assinatura"
# ==============================================================================
@router.get(
    "/api/empresa/minha",
    response_model=schemas.EmpresaOut,
    tags=["empresa"],
)
def minha_empresa(
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN, USER)),
):
    empresa = db.get(models.Empresa, atual.empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    total_cameras = db.query(models.Camera).filter(models.Camera.empresa_id == empresa.id).count()
    item = schemas.EmpresaOut.model_validate(empresa)
    item.total_cameras = total_cameras
    return item


# ==============================================================================
# CÂMERAS
#   - SUPER_ADMIN: CRUD completo, em qualquer empresa.
#   - ADMIN/USER: CRUD completo, restrito à própria empresa (isolamento
#     absoluto — nunca enxergam nem manipulam câmeras de outra empresa).
# ==============================================================================
def _obter_camera_acessivel(db: Session, camera_id: int, atual: models.Usuario) -> models.Camera:
    """Retorna a câmera se o SUPER_ADMIN pedir qualquer uma, ou se pertencer à empresa do usuário atual."""
    camera = db.get(models.Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Câmera não encontrada")
    if atual.role != SUPER_ADMIN and camera.empresa_id != atual.empresa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Câmera não encontrada")
    return camera


@router.get("/api/admin/cameras", response_model=list[schemas.CameraOut], tags=["cameras"])
def listar_cameras(
    empresa_id: Optional[int] = Query(default=None, description="SUPER_ADMIN: filtra por empresa"),
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(get_current_usuario),
):
    garantir_assinatura_ativa(atual)
    query = db.query(models.Camera)
    if atual.role == SUPER_ADMIN:
        if empresa_id is not None:
            query = query.filter(models.Camera.empresa_id == empresa_id)
        # sem filtro: SUPER_ADMIN vê as câmeras de todas as empresas
    else:
        query = query.filter(models.Camera.empresa_id == atual.empresa_id)
    return query.order_by(models.Camera.id).all()


@router.post(
    "/api/admin/cameras",
    response_model=schemas.CameraOut,
    status_code=status.HTTP_201_CREATED,
    tags=["cameras"],
)
def criar_camera(
    payload: schemas.CameraCreate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(SUPER_ADMIN, ADMIN, USER)),
):
    garantir_assinatura_ativa(atual)

    if atual.role == SUPER_ADMIN:
        empresa_id = payload.empresa_id
        if not empresa_id or not db.get(models.Empresa, empresa_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa informada não existe")
    else:
        # ADMIN/USER só criam câmera na própria empresa — payload.empresa_id é ignorado.
        empresa_id = atual.empresa_id

    camera = models.Camera(
        empresa_id=empresa_id,
        nome_camera=payload.nome_camera,
        rtsp_url=payload.rtsp_url,
        perfil_ativo=payload.perfil_ativo,
        status=models.StatusCamera.offline,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.put("/api/admin/cameras/{camera_id}", response_model=schemas.CameraOut, tags=["cameras"])
def atualizar_camera(
    camera_id: int,
    payload: schemas.CameraUpdate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(SUPER_ADMIN, ADMIN, USER)),
):
    garantir_assinatura_ativa(atual)
    camera = _obter_camera_acessivel(db, camera_id, atual)

    if payload.nome_camera is not None:
        camera.nome_camera = payload.nome_camera
    if payload.rtsp_url is not None and payload.rtsp_url != camera.rtsp_url:
        # Só recicla o processor quando a fonte MUDOU de verdade — o formulário do
        # frontend sempre manda `rtsp_url` no payload (mudando ou não), e reciclar à
        # toa descarta um VideoProcessor já "quente" (modelo YOLO já carregado —
        # import do ultralytics medido em ~30s em produção, ver config.py) só pra
        # forçar outro carregamento do zero sem necessidade nenhuma.
        camera.rtsp_url = payload.rtsp_url
        camera_manager.stop(camera.id)  # força reconexão com a nova URL
    if payload.perfil_ativo is not None:
        camera.perfil_ativo = payload.perfil_ativo
    if payload.status is not None:
        camera.status = payload.status

    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/api/admin/cameras/{camera_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["cameras"])
def remover_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(SUPER_ADMIN, ADMIN, USER)),
):
    garantir_assinatura_ativa(atual)
    camera = _obter_camera_acessivel(db, camera_id, atual)
    camera_manager.stop(camera.id)
    db.delete(camera)
    db.commit()


# ==============================================================================
# ZONAS
#   - SUPER_ADMIN, ADMIN e USER podem desenhar/editar zonas das câmeras que
#     conseguem acessar (mesma regra de isolamento de `_obter_camera_acessivel`).
# ==============================================================================
@router.post(
    "/api/admin/cameras/{camera_id}/zonas",
    response_model=list[schemas.ZonaOut],
    tags=["zonas"],
)
def salvar_zonas(
    camera_id: int,
    payload: schemas.ZonasBulkCreate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(SUPER_ADMIN, ADMIN, USER)),
):
    """Substitui todas as zonas da câmera pelas informadas (o frontend envia o estado completo do desenho)."""
    garantir_assinatura_ativa(atual)
    camera = _obter_camera_acessivel(db, camera_id, atual)

    db.query(models.Zona).filter(models.Zona.camera_id == camera.id).delete()

    novas_zonas = []
    for zona_in in payload.zonas:
        zona = models.Zona(
            camera_id=camera.id,
            tipo_zona=zona_in.tipo_zona,
            coordenadas_json=json.dumps(zona_in.coordenadas),
        )
        db.add(zona)
        novas_zonas.append(zona)

    db.commit()
    for z in novas_zonas:
        db.refresh(z)

    # Se a câmera já estiver com streaming ativo, atualiza as zonas em tempo real.
    camera_manager.stop(camera.id)

    return [
        schemas.ZonaOut(
            id=z.id, camera_id=z.camera_id, tipo_zona=z.tipo_zona, coordenadas=json.loads(z.coordenadas_json)
        )
        for z in novas_zonas
    ]


@router.get(
    "/api/admin/cameras/{camera_id}/zonas",
    response_model=list[schemas.ZonaOut],
    tags=["zonas"],
)
def listar_zonas(
    camera_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(SUPER_ADMIN, ADMIN, USER)),
):
    garantir_assinatura_ativa(atual)
    camera = _obter_camera_acessivel(db, camera_id, atual)
    zonas = db.query(models.Zona).filter(models.Zona.camera_id == camera.id).all()
    return [
        schemas.ZonaOut(
            id=z.id, camera_id=z.camera_id, tipo_zona=z.tipo_zona, coordenadas=json.loads(z.coordenadas_json)
        )
        for z in zonas
    ]


# ==============================================================================
# STREAMING DE VÍDEO (MJPEG, com blur de anonimização aplicado)
#   - ADMIN/USER só acessam as próprias câmeras. SUPER_ADMIN acessa qualquer uma.
# ==============================================================================
@router.get("/api/video_feed/{camera_id}", tags=["video"])
def video_feed(
    camera_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(get_current_usuario_stream),
):
    garantir_assinatura_ativa(atual)
    camera = _obter_camera_acessivel(db, camera_id, atual)
    zonas = db.query(models.Zona).filter(models.Zona.camera_id == camera.id).all()

    # NÃO marcamos `camera.status = online` aqui: isso só significava "essa rota foi
    # requisitada", não que a captura de fato conseguiu abrir/ler a câmera — uma fonte
    # que nunca conecta (ex.: índice de webcam local num servidor sem câmera nenhuma)
    # ainda aparecia como "online" no dashboard enquanto a tela ficava preta. O status
    # real agora é mantido por VideoProcessor._atualizar_status_camera, refletindo se
    # CameraStream está de fato entregando frames (ver vision.py).
    processador = camera_manager.get_or_create(camera, zonas, SessionLocal)

    if (camera.rtsp_url or "").strip().lower() == FONTE_WEBCAM_NAVEGADOR:
        # Caminho DIRETO e definitivo: serve o último frame recebido em
        # camera_ingest com um cv2.blur genérico, sem depender do modelo YOLO
        # nem da thread de processamento assíncrono de VideoProcessor — ver
        # vision.gerar_mjpeg_bruto_com_blur. Câmeras RTSP/webcam local continuam
        # no pipeline completo (generate_mjpeg) logo abaixo.
        return StreamingResponse(
            vision.gerar_mjpeg_bruto_com_blur(camera.id),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return StreamingResponse(
        processador.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# Tamanho máximo aceito por frame recebido via WebSocket em camera_ingest — um
# JPEG 640x480 de qualidade normal fica na casa de dezenas de KB; alguns MB já é
# folga generosa. Descarta silenciosamente qualquer coisa maior em vez de deixar
# um payload gigante ser decodificado (a rota já exige JWT + assinatura ativa +
# posse da câmera, então isso é defesa em profundidade, não a barreira principal).
_CAMERA_INGEST_MAX_FRAME_BYTES = 4 * 1024 * 1024


@router.websocket("/api/camera_ingest/{camera_id}")
async def camera_ingest(websocket: WebSocket, camera_id: int):
    """
    Contrapartida de ENTRADA do /api/video_feed (que é a saída, já processada):
    recebe, via WebSocket, os frames JPEG que o NAVEGADOR do usuário capturou da
    própria webcam (getUserMedia) e empurra pro VideoProcessor desta câmera — ver
    vision.BrowserPushStream. Só existe porque, com o backend rodando num
    servidor remoto (Render), NENHUMA webcam local do usuário é alcançável por
    `cv2.VideoCapture`; quem tem acesso de verdade à câmera é o navegador de
    quem está com o notebook na mão, então é ele quem precisa mandar os frames
    pra cá — o resto do pipeline (YOLO, zonas, blur, streaming de saída) não
    muda nada, só a origem do frame.

    Autenticação via `?token=` (mesma razão do get_current_usuario_stream: não
    dá pra mandar um header Authorization ao abrir um WebSocket do navegador com
    o construtor nativo `new WebSocket(url)`). Feita manualmente aqui (em vez de
    `Depends`) para controlar explicitamente o fechamento da conexão em cada
    falha, sem depender de como cada versão do FastAPI traduz uma HTTPException
    levantada dentro de uma dependency de rota WebSocket.
    """
    token = websocket.query_params.get("token")
    db = SessionLocal()
    try:
        try:
            atual = _resolve_usuario_from_token(token, db)
            garantir_assinatura_ativa(atual)
            camera = _obter_camera_acessivel(db, camera_id, atual)
        except HTTPException as exc:
            logger.warning("[camera %s] camera_ingest recusado: %s", camera_id, exc.detail)
            await websocket.close(code=4401)
            return

        if (camera.rtsp_url or "").strip().lower() != FONTE_WEBCAM_NAVEGADOR:
            logger.warning(
                "[camera %s] camera_ingest recusado: rtsp_url não é \"%s\" (é %r).",
                camera_id, FONTE_WEBCAM_NAVEGADOR, camera.rtsp_url,
            )
            await websocket.close(code=4400)
            return

        zonas = db.query(models.Zona).filter(models.Zona.camera_id == camera.id).all()
        processador = camera_manager.get_or_create(camera, zonas, SessionLocal)
    finally:
        db.close()

    if not isinstance(processador.stream, BrowserPushStream):
        # Só acontece se a câmera foi trocada de RTSP/webcam-local pra "browser"
        # sem o processor antigo ser reciclado (atualizar_camera já chama
        # camera_manager.stop() quando rtsp_url muda — ver routes.py — então isso
        # não deveria ocorrer em uso normal; é rede de segurança).
        logger.error("[camera %s] camera_ingest: processor ativo não é BrowserPushStream.", camera_id)
        await websocket.close(code=4409)
        return

    await websocket.accept()
    logger.info("[camera %s] navegador conectado em camera_ingest — recebendo frames.", camera_id)
    frames_recebidos = 0
    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) > _CAMERA_INGEST_MAX_FRAME_BYTES:
                logger.warning("[camera %s] frame recebido (%d bytes) excede o limite — descartado.", camera_id, len(data))
                continue
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                logger.warning("[camera %s] frame recebido (%d bytes) não pôde ser decodificado — descartado.", camera_id, len(data))
                continue
            # Caminho DIRETO e definitivo (bypass do YOLO) usado por /api/video_feed
            # — ver docstring de vision.gerar_mjpeg_bruto_com_blur. Gravação simples
            # em dict global com lock, sem fila nem thread própria.
            vision.armazenar_frame_bruto(camera_id, frame)
            # Pipeline de IA (analytics de fila/atendimento/estagnação) continua
            # recebendo o frame normalmente — só a EXIBIÇÃO do vídeo não depende
            # mais dele.
            processador.stream.push_frame(frame)
            frames_recebidos += 1
            if frames_recebidos == 1:
                # Só o primeiro: a ~5fps um log por frame afogaria o resto do log.
                # Sinaliza claramente "sim, o frame chegou e foi decodificado" —
                # se isso aparece mas o vídeo não carrega, o problema está do lado
                # do PROCESSAMENTO/entrega (ver logs de _carregar_modelo e
                # generate_mjpeg), não da recepção.
                logger.info("[camera %s] primeiro frame decodificado e entregue ao processador (shape=%s).", camera_id, frame.shape)
    except WebSocketDisconnect:
        logger.info("[camera %s] navegador desconectou de camera_ingest (recebeu %d frames).", camera_id, frames_recebidos)


# ==============================================================================
# MÉTRICAS / DASHBOARD
#   - ADMIN/USER só consultam a própria empresa. SUPER_ADMIN consulta qualquer
#     uma (usado no painel admin para abrir o dashboard de qualquer empresa).
# ==============================================================================
def _resolver_periodo_dashboard(periodo: str) -> tuple[datetime, datetime, date]:
    """
    Converte o filtro rápido do frontend ("hoje" | "7d" | "30d") num intervalo
    [inicio, fim] de datetimes (UTC, mesma referência de `MetricaAtendimento.timestamp`
    etc.). "hoje" preserva o comportamento anterior a este filtro (00:00 a
    23:59:59.999999 do dia corrente); "7d"/"30d" contam hoje + os N-1 dias
    anteriores. Também devolve a data de hoje, usada em `data_referencia`.
    """
    hoje = datetime.utcnow().date()
    fim = datetime.combine(hoje, dt_time.max)
    dias_anteriores = {"hoje": 0, "7d": 6, "30d": 29}.get(periodo, 0)
    inicio = datetime.combine(hoje - timedelta(days=dias_anteriores), dt_time.min)
    return inicio, fim, hoje


def _calcular_metricas_fila(
    atendimentos: list[models.MetricaAtendimento], alertas: list[models.AlertaFila]
) -> schemas.MetricasFila:
    """Dashboard Analytics Tópico 1 — Perda de Vendas & Gargalos de Atendimento."""
    total_sessoes = len(atendimentos)
    esperas = [a.tempo_espera_segundos for a in atendimentos if a.tempo_espera_segundos is not None]
    total_desistencias = sum(1 for a in atendimentos if a.desistiu)

    return schemas.MetricasFila(
        tempo_medio_espera_segundos=round(sum(esperas) / len(esperas), 2) if esperas else 0.0,
        total_clientes_na_fila=total_sessoes,
        total_desistencias=total_desistencias,
        taxa_desistencia_pct=round(total_desistencias / total_sessoes * 100, 2) if total_sessoes else 0.0,
        picos_fila_sem_atendente=len(alertas),
    )


def _calcular_metricas_equipe(amostras: list[models.AmostraBalcao]) -> schemas.MetricasEquipe:
    """
    Dashboard Analytics Tópico 2 — Eficiência e Desempenho da Equipe. Derivado por
    amostragem (models.AmostraBalcao, uma linha a cada OCUPACAO_AMOSTRA_SEGUNDOS) —
    não há um relógio contínuo por atendente, então "tempo no posto"/"tempo em
    atendimento" são estimados como (nº de amostras que satisfazem a condição) x
    (intervalo entre amostras).
    """
    intervalo = config.OCUPACAO_AMOSTRA_SEGUNDOS
    total_amostras = len(amostras)
    amostras_com_atendente = [a for a in amostras if a.atendentes_presentes > 0]
    amostras_em_atendimento = [
        a for a in amostras if a.atendentes_presentes > 0 and a.clientes_presentes > 0
    ]

    tempo_no_posto = len(amostras_com_atendente) * intervalo
    tempo_em_atendimento = len(amostras_em_atendimento) * intervalo

    por_hora = defaultdict(list)
    for a in amostras:
        por_hora[a.timestamp.hour].append(a)
    distribuicao_por_hora = [
        schemas.PresencaPorHora(
            hora=h,
            media_atendentes_presentes=round(sum(x.atendentes_presentes for x in xs) / len(xs), 2),
            media_clientes_presentes=round(sum(x.clientes_presentes for x in xs) / len(xs), 2),
        )
        for h, xs in sorted(por_hora.items())
    ]

    return schemas.MetricasEquipe(
        taxa_ociosidade_balcao_pct=(
            round((total_amostras - len(amostras_com_atendente)) / total_amostras * 100, 2)
            if total_amostras
            else 0.0
        ),
        tempo_no_posto_segundos=round(tempo_no_posto, 2),
        tempo_em_atendimento_segundos=round(tempo_em_atendimento, 2),
        ratio_atendimento_pct=round(tempo_em_atendimento / tempo_no_posto * 100, 2) if tempo_no_posto else None,
        distribuicao_por_hora=distribuicao_por_hora,
    )


def _calcular_ranking_cameras(
    cameras: list[models.Camera],
    atendimentos: list[models.MetricaAtendimento],
    amostras: list[models.AmostraBalcao],
) -> schemas.RankingZonas:
    """
    Dashboard Analytics Tópico 4 — Ranking e Comparativo por Câmera. A granularidade
    é por câmera (não por zona individual): o schema hoje não grava a qual zona uma
    sessão de fila pertence — cada câmera de perfil balcão tem uma 'Zona Cliente' e
    uma 'Zona Atendente', então câmera já equivale a um ponto de atendimento.
    """
    tabela: list[schemas.RankingCameraItem] = []
    for cam in cameras:
        atend_cam = [a for a in atendimentos if a.camera_id == cam.id]
        amostras_cam = [a for a in amostras if a.camera_id == cam.id]

        concluidos = [a for a in atend_cam if a.concluido]
        esperas = [a.tempo_espera_segundos for a in atend_cam if a.tempo_espera_segundos is not None]
        desistencias = sum(1 for a in atend_cam if a.desistiu)
        amostras_com_atendente = [a for a in amostras_cam if a.atendentes_presentes > 0]

        tabela.append(
            schemas.RankingCameraItem(
                camera_id=cam.id,
                nome_camera=cam.nome_camera,
                total_atendimentos_concluidos=len(concluidos),
                tempo_medio_atendimento_segundos=(
                    round(sum(a.duracao_segundos for a in concluidos) / len(concluidos), 2) if concluidos else 0.0
                ),
                tempo_medio_espera_segundos=round(sum(esperas) / len(esperas), 2) if esperas else None,
                taxa_desistencia_pct=(
                    round(desistencias / len(atend_cam) * 100, 2) if atend_cam else 0.0
                ),
                taxa_ociosidade_pct=(
                    round((len(amostras_cam) - len(amostras_com_atendente)) / len(amostras_cam) * 100, 2)
                    if amostras_cam
                    else None
                ),
            )
        )

    com_espera = [c for c in tabela if c.tempo_medio_espera_segundos is not None]
    mais_rapida = min(com_espera, key=lambda c: c.tempo_medio_espera_segundos, default=None)

    com_desistencia = [c for c in tabela if c.taxa_desistencia_pct > 0]
    maior_perda = max(com_desistencia, key=lambda c: c.taxa_desistencia_pct, default=None)

    return schemas.RankingZonas(
        tabela=tabela,
        camera_mais_rapida_id=mais_rapida.camera_id if mais_rapida else None,
        camera_maior_desistencia_id=maior_perda.camera_id if maior_perda else None,
    )


@router.get("/api/metrics/dashboard/{empresa_id}", response_model=schemas.DashboardMetrics, tags=["metrics"])
def dashboard_metrics(
    empresa_id: int,
    periodo: str = Query(
        "hoje", pattern="^(hoje|7d|30d)$", description="Intervalo rápido: 'hoje', '7d' (7 dias) ou '30d' (30 dias)"
    ),
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(get_current_usuario),
):
    garantir_assinatura_ativa(atual)
    if atual.role != SUPER_ADMIN and empresa_id != atual.empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado a métricas de outra empresa")

    if not db.get(models.Empresa, empresa_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")

    inicio, fim, hoje = _resolver_periodo_dashboard(periodo)

    atendimentos = (
        db.query(models.MetricaAtendimento)
        .filter(
            models.MetricaAtendimento.empresa_id == empresa_id,
            models.MetricaAtendimento.timestamp.between(inicio, fim),
        )
        .all()
    )
    ocupacoes = (
        db.query(models.MetricaOcupacao)
        .filter(
            models.MetricaOcupacao.empresa_id == empresa_id,
            models.MetricaOcupacao.timestamp.between(inicio, fim),
        )
        .all()
    )
    amostras_balcao = (
        db.query(models.AmostraBalcao)
        .filter(
            models.AmostraBalcao.empresa_id == empresa_id,
            models.AmostraBalcao.timestamp.between(inicio, fim),
        )
        .all()
    )
    alertas_fila = (
        db.query(models.AlertaFila)
        .filter(
            models.AlertaFila.empresa_id == empresa_id,
            models.AlertaFila.timestamp.between(inicio, fim),
        )
        .all()
    )

    total_atendimentos = len(atendimentos)
    concluidos = sum(1 for a in atendimentos if a.concluido)
    abandonados = total_atendimentos - concluidos
    tempo_medio = (
        sum(a.duracao_segundos for a in atendimentos) / total_atendimentos if total_atendimentos else 0.0
    )

    pico_pessoas = max((o.pessoas_detectadas for o in ocupacoes), default=0)
    media_pessoas = (
        sum(o.pessoas_detectadas for o in ocupacoes) / len(ocupacoes) if ocupacoes else 0.0
    )
    tempo_total_inatividade = sum(o.tempo_inatividade_segundos for o in ocupacoes)

    # Horários de pico: contagem de eventos de atendimento por hora do dia
    contagem_por_hora = defaultdict(int)
    for a in atendimentos:
        contagem_por_hora[a.timestamp.hour] += 1
    horarios_pico = [
        schemas.HorarioPico(hora=h, total_eventos=c)
        for h, c in sorted(contagem_por_hora.items(), key=lambda item: item[1], reverse=True)
    ]

    # Fluxo de ocupação ao longo do turno: média de pessoas detectadas por hora do dia
    pessoas_por_hora = defaultdict(list)
    for o in ocupacoes:
        pessoas_por_hora[o.timestamp.hour].append(o.pessoas_detectadas)
    ocupacao_por_hora = [
        schemas.OcupacaoPorHora(hora=h, media_pessoas=round(sum(valores) / len(valores), 2))
        for h, valores in sorted(pessoas_por_hora.items())
    ]

    # Quebra por câmera
    cameras = db.query(models.Camera).filter(models.Camera.empresa_id == empresa_id).all()
    por_camera = {}
    for cam in cameras:
        atend_cam = [a for a in atendimentos if a.camera_id == cam.id]
        ocup_cam = [o for o in ocupacoes if o.camera_id == cam.id]
        por_camera[cam.id] = schemas.MetricasPorCamera(
            nome_camera=cam.nome_camera,
            total_atendimentos=len(atend_cam),
            tempo_medio_atendimento_segundos=(
                sum(a.duracao_segundos for a in atend_cam) / len(atend_cam) if atend_cam else 0.0
            ),
            media_pessoas_detectadas=(
                sum(o.pessoas_detectadas for o in ocup_cam) / len(ocup_cam) if ocup_cam else 0.0
            ),
        )

    return schemas.DashboardMetrics(
        empresa_id=empresa_id,
        data_referencia=hoje.isoformat(),
        periodo=periodo,
        total_atendimentos=total_atendimentos,
        atendimentos_concluidos=concluidos,
        atendimentos_abandonados=abandonados,
        tempo_medio_atendimento_segundos=round(tempo_medio, 2),
        pico_pessoas_detectadas=pico_pessoas,
        media_pessoas_detectadas=round(media_pessoas, 2),
        tempo_total_inatividade_segundos=round(tempo_total_inatividade, 2),
        horarios_pico=horarios_pico,
        ocupacao_por_hora=ocupacao_por_hora,
        por_camera=por_camera,
        fila=_calcular_metricas_fila(atendimentos, alertas_fila),
        equipe=_calcular_metricas_equipe(amostras_balcao),
        ranking=_calcular_ranking_cameras(cameras, atendimentos, amostras_balcao),
    )


# ==============================================================================
# RELATÓRIOS EXPORTÁVEIS (PDF executivo via ReportLab, Excel via Pandas+OpenPyXL)
#   - Mesma regra de acesso do dashboard: ADMIN/USER só exportam a própria
#     empresa, SUPER_ADMIN exporta qualquer uma.
# ==============================================================================
_MAX_DIAS_RELATORIO = 366


def _resolver_periodo_relatorio(data_inicio: Optional[date], data_fim: Optional[date]) -> tuple[date, date]:
    """Sem parâmetros, o período padrão é 'hoje' (equivalente ao filtro rápido do frontend)."""
    hoje = datetime.utcnow().date()
    inicio = data_inicio or hoje
    fim = data_fim or hoje
    if fim < inicio:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="data_fim não pode ser anterior a data_inicio")
    if (fim - inicio).days > _MAX_DIAS_RELATORIO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Período máximo suportado: {_MAX_DIAS_RELATORIO} dias"
        )
    return inicio, fim


def _obter_empresa_para_relatorio(db: Session, empresa_id: int, atual: models.Usuario) -> models.Empresa:
    if atual.role != SUPER_ADMIN and empresa_id != atual.empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado a relatórios de outra empresa")
    empresa = db.get(models.Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    return empresa


@router.get("/api/reports/pdf/{empresa_id}", tags=["reports"])
def relatorio_pdf(
    empresa_id: int,
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(get_current_usuario),
):
    garantir_assinatura_ativa(atual)
    empresa = _obter_empresa_para_relatorio(db, empresa_id, atual)
    inicio, fim = _resolver_periodo_relatorio(data_inicio, data_fim)

    dados = reports.coletar_dados(db, empresa, inicio, fim)
    pdf_bytes = reports.gerar_pdf(dados)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{reports.nome_arquivo(dados, "pdf")}"'},
    )


@router.get("/api/reports/excel/{empresa_id}", tags=["reports"])
def relatorio_excel(
    empresa_id: int,
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(get_current_usuario),
):
    garantir_assinatura_ativa(atual)
    empresa = _obter_empresa_para_relatorio(db, empresa_id, atual)
    inicio, fim = _resolver_periodo_relatorio(data_inicio, data_fim)

    dados = reports.coletar_dados(db, empresa, inicio, fim)
    excel_bytes = reports.gerar_excel(dados)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{reports.nome_arquivo(dados, "xlsx")}"'},
    )


# ==============================================================================
# PAGAMENTOS (Stripe) — Checkout, Customer Portal e Webhook
# ==============================================================================
@router.post(
    "/api/payments/create-checkout-session",
    response_model=schemas.CheckoutSessionOut,
    tags=["payments"],
)
def create_checkout_session(
    payload: schemas.CheckoutSessionRequest,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN)),
):
    empresa = db.get(models.Empresa, atual.empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    try:
        url = payments.criar_checkout_session(db, empresa, payload.plano, atual.email)
    except payments.StripeNaoConfigurado as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return schemas.CheckoutSessionOut(checkout_url=url)


@router.post(
    "/api/payments/customer-portal",
    response_model=schemas.CustomerPortalOut,
    tags=["payments"],
)
def customer_portal(
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_roles(ADMIN)),
):
    empresa = db.get(models.Empresa, atual.empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa não encontrada")
    try:
        portal_url, checkout_url = payments.criar_portal_ou_checkout_session(db, empresa, atual.email)
    except payments.StripeNaoConfigurado as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        # Sem isto, uma exceção não prevista (Stripe ou banco) vira o 500
        # plain-text padrão do Starlette — sem corpo JSON, o frontend perde
        # o `detail` e mostra sempre a mensagem genérica. Loga o traceback
        # completo (aparece no dashboard do Render) e devolve um detail real.
        logger.exception(
            "customer-portal: erro não tratado para empresa_id=%s", empresa.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível abrir o portal de assinatura ({type(exc).__name__}: {exc})",
        ) from exc

    if not portal_url and not checkout_url:
        logger.error(
            "customer-portal: nem portal_url nem checkout_url voltaram para empresa_id=%s",
            empresa.id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A Stripe não retornou uma URL válida. Tente novamente em instantes.",
        )

    logger.info(
        "customer-portal: resposta OK para empresa_id=%s (portal=%s, checkout=%s)",
        empresa.id, bool(portal_url), bool(checkout_url),
    )
    return schemas.CustomerPortalOut(portal_url=portal_url, checkout_url=checkout_url)


@router.post("/api/webhooks/stripe", tags=["payments"], include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint público (sem JWT) chamado pela Stripe. A autenticidade é validada
    pela assinatura do payload (header `stripe-signature` + STRIPE_WEBHOOK_SECRET),
    não por login — é assim que toda integração de webhook da Stripe funciona.
    """
    payload = await request.body()
    assinatura = request.headers.get("stripe-signature")
    try:
        event = payments.construir_evento_webhook(payload, assinatura)
    except payments.StripeNaoConfigurado as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assinatura de webhook inválida")

    payments.processar_evento_webhook(db, event)
    return {"received": True}
