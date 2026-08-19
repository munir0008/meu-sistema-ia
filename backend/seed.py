"""
Seeder de dados de teste — popula o banco com contas e uma câmera de exemplo
prontas para o passo a passo de teste com webcam (ver README na raiz do projeto
ou a saída do `run_app.py`).

Idempotente: pode ser rodado várias vezes sem duplicar registros (verifica por
email/câmera antes de criar). Independente do bootstrap automático de
SUPER_ADMIN que já roda no startup do backend (`database.seed_super_admin`,
guiado por `SUPER_ADMIN_EMAIL`/`SUPER_ADMIN_PASSWORD` do .env) — este script
cria explicitamente as contas de demonstração pedidas, com credenciais fixas:

    SUPER_ADMIN       admin@sistema.com     / senha123
    Padaria Silva     gerente@padaria.com   / cliente123   (ADMIN)
    Escritório Santos gerente@escritorio.com/ cliente123   (ADMIN)

Uso:
    python seed.py            (a partir de backend/)
    python ../seed.py         (chamado por run_app.py na raiz do projeto)
"""
import os
import sys
from pathlib import Path

# Garante que os imports (config, database, models, auth) resolvam e que o
# caminho relativo do SQLite (DATABASE_URL) aponte sempre para backend/,
# não importa de onde o script foi chamado.
os.chdir(Path(__file__).resolve().parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth import hash_password  # noqa: E402
from database import SessionLocal, init_db  # noqa: E402
import models  # noqa: E402

SUPER_ADMIN = {"email": "admin@sistema.com", "senha": "senha123"}

EMPRESAS = [
    {"nome_empresa": "Padaria Silva", "email": "gerente@padaria.com", "senha": "cliente123"},
    {"nome_empresa": "Escritório Santos", "email": "gerente@escritorio.com", "senha": "cliente123"},
]

CAMERA_PADARIA = {
    "nome_camera": "Balcão Principal (Webcam)",
    "rtsp_url": "0",  # índice 0 = webcam local do computador
    "perfil_ativo": models.PerfilCamera.balcao_loja,
}


def _obter_ou_criar_super_admin(db) -> None:
    usuario = db.query(models.Usuario).filter(models.Usuario.email == SUPER_ADMIN["email"]).first()
    if usuario:
        print(f"  já existe: {SUPER_ADMIN['email']} (SUPER_ADMIN) — nada a fazer")
        return
    usuario = models.Usuario(
        empresa_id=None,
        nome="Administrador",
        email=SUPER_ADMIN["email"],
        senha_hash=hash_password(SUPER_ADMIN["senha"]),
        role=models.RoleUsuario.super_admin,
    )
    db.add(usuario)
    db.commit()
    print(f"  criado: {SUPER_ADMIN['email']} (SUPER_ADMIN)")


def _obter_ou_criar_empresa(db, dados: dict) -> tuple[models.Empresa, bool]:
    usuario = db.query(models.Usuario).filter(models.Usuario.email == dados["email"]).first()
    if usuario:
        print(f"  já existe: {dados['email']} (ADMIN) — nada a fazer")
        return usuario.empresa, False

    empresa = models.Empresa(
        nome_empresa=dados["nome_empresa"],
        status_assinatura=models.StatusAssinatura.trial,
    )
    db.add(empresa)
    db.flush()

    usuario = models.Usuario(
        empresa_id=empresa.id,
        nome="Gerente",
        email=dados["email"],
        senha_hash=hash_password(dados["senha"]),
        role=models.RoleUsuario.admin,
    )
    db.add(usuario)
    db.commit()
    db.refresh(empresa)
    print(f"  criado: {dados['nome_empresa']} <{dados['email']}> (ADMIN)")
    return empresa, True


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        print("1/3 — Conta SUPER_ADMIN")
        _obter_ou_criar_super_admin(db)

        print("2/3 — Empresas de exemplo")
        padaria, _ = _obter_ou_criar_empresa(db, EMPRESAS[0])
        _obter_ou_criar_empresa(db, EMPRESAS[1])

        print("3/3 — Câmera inicial (webcam local, índice 0) para a Padaria Silva")
        camera_existente = (
            db.query(models.Camera)
            .filter(models.Camera.empresa_id == padaria.id, models.Camera.rtsp_url == "0")
            .first()
        )
        if camera_existente:
            print(f"  já existe: {camera_existente.nome_camera} — nada a fazer")
        else:
            camera = models.Camera(empresa_id=padaria.id, **CAMERA_PADARIA)
            db.add(camera)
            db.commit()
            print(f"  criada: {CAMERA_PADARIA['nome_camera']} -> {padaria.nome_empresa}")
    finally:
        db.close()

    _imprimir_resumo()


def _imprimir_resumo() -> None:
    largura = 64
    print("\n" + "=" * largura)
    print("DADOS DE TESTE PRONTOS".center(largura))
    print("=" * largura)
    print(f"  SUPER_ADMIN        : {SUPER_ADMIN['email']:<28} / {SUPER_ADMIN['senha']}")
    print(f"  Padaria Silva       : {EMPRESAS[0]['email']:<28} / {EMPRESAS[0]['senha']}")
    print(f"  Escritório Santos   : {EMPRESAS[1]['email']:<28} / {EMPRESAS[1]['senha']}")
    print(f"  Câmera inicial      : {CAMERA_PADARIA['nome_camera']} (webcam índice 0)")
    print("=" * largura)


if __name__ == "__main__":
    seed()
