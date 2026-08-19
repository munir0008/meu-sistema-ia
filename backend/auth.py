"""
Utilidades de autenticação (JWT + hashing de senha) e autorização (RBAC).

RBAC: o JWT emitido no login/signup carrega os claims `usuario_id`, `role`
(SUPER_ADMIN | ADMIN | USER) e `empresa_id` (nulo para SUPER_ADMIN). Cada rota
protegida depende de `get_current_usuario` (valida o JWT) e, quando a ação é
restrita, de `require_roles(...)` (valida o papel) — juntos funcionam como o
"middleware" de autenticação/autorização de cada request (implementado como
dependency, o equivalente idiomático a middleware por rota na FastAPI).
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Usamos o pacote `bcrypt` diretamente (em vez de passlib.CryptContext) para evitar
# a incompatibilidade conhecida entre passlib<=1.7.4 e bcrypt>=4.1 (passlib tenta ler
# `bcrypt.__about__.__version__`, removido nas versões novas do bcrypt).
_BCRYPT_MAX_BYTES = 72  # limite do algoritmo bcrypt


def verify_password(plain: str, hashed: str) -> bool:
    senha_bytes = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(senha_bytes, hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    senha_bytes = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(senha_bytes, bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def criar_token_para_usuario(usuario: "models.Usuario") -> str:
    """Gera o JWT padrão de sessão, com `role`/`empresa_id` embutidos para uso no RBAC."""
    role_valor = usuario.role.value if hasattr(usuario.role, "value") else usuario.role
    return create_access_token(
        {
            "sub": usuario.email,
            "usuario_id": usuario.id,
            "empresa_id": usuario.empresa_id,
            "role": role_valor,
        }
    )


def _resolve_usuario_from_token(token: Optional[str], db: Session) -> models.Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = payload.get("usuario_id")
        if usuario_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if usuario is None:
        raise credentials_exception
    return usuario


def get_current_usuario(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.Usuario:
    """
    Resolve a conta autenticada a partir do JWT (Bearer token, via header Authorization).
    É a validação central de token aplicada a toda rota protegida — o papel (`role`) é
    sempre relido do banco (não confiamos apenas no claim do token), então uma troca de
    papel/plano feita pelo SUPER_ADMIN vale imediatamente na próxima requisição.
    """
    return _resolve_usuario_from_token(token, db)


_oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_usuario_stream(
    token_header: Optional[str] = Depends(_oauth2_scheme_optional),
    token_query: Optional[str] = Query(default=None, alias="token"),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """
    Mesma resolução de `get_current_usuario`, mas também aceita o JWT via query string
    (?token=...). Necessário exclusivamente para o streaming MJPEG: uma tag <img>/<video>
    do navegador não consegue enviar o header Authorization, então o token precisa
    trafegar na própria URL nesse caso específico.
    """
    return _resolve_usuario_from_token(token_header or token_query, db)


def require_roles(*roles: models.RoleUsuario):
    """
    Factory de dependency para RBAC: garante que a conta autenticada tenha um dos
    papéis informados, retornando 403 caso contrário. Uso:

        @router.get(..., dependencies=[Depends(require_roles(RoleUsuario.super_admin))])
        # ou, quando a rota também precisa do objeto usuario:
        def rota(usuario: models.Usuario = Depends(require_roles(RoleUsuario.super_admin))): ...
    """

    def dependency(usuario: models.Usuario = Depends(get_current_usuario)) -> models.Usuario:
        if usuario.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso",
            )
        return usuario

    return dependency


def is_super_admin(usuario: models.Usuario) -> bool:
    return usuario.role == models.RoleUsuario.super_admin


_ASSINATURAS_VALIDAS = (models.StatusAssinatura.trial, models.StatusAssinatura.active)


def garantir_assinatura_ativa(usuario: "models.Usuario") -> None:
    """
    Bloqueia o acesso a rotas de negócio (câmeras, zonas, streaming, métricas,
    relatórios) quando a empresa do usuário não está em trial nem com a
    assinatura ativa. SUPER_ADMIN nunca é bloqueado (é uma conta global, sem
    empresa/assinatura).

    O `detail` é um objeto (não uma string) de propósito: o frontend usa
    `detail.code` para diferenciar esse 403 de qualquer outro e redirecionar
    automaticamente para a página de planos (ver api/client.js).
    """
    if usuario.role == models.RoleUsuario.super_admin:
        return
    empresa = usuario.empresa
    status_atual = empresa.status_assinatura if empresa else None
    if status_atual not in _ASSINATURAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "subscription_required",
                "message": "Sua assinatura não está ativa. Escolha um plano para continuar.",
                "status_assinatura": status_atual.value if status_atual else None,
            },
        )
