"""
Configuração da conexão com o banco de dados (SQLite) via SQLAlchemy.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI: entrega uma sessão de banco por request e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrar_para_multi_tenant() -> None:
    """
    Migração de esquema: a versão anterior do banco tinha uma única tabela
    `clientes` (empresa + login misturados) e `cameras`/`metricas_*` com a
    coluna `cliente_id`. Esta migração separa isso em `empresas` (tenant +
    billing) e `usuarios` (login/RBAC), preservando todo dado existente —
    incluindo a(s) conta(s) SUPER_ADMIN.

    Só roda uma vez: a marca de "já migrado" é a própria tabela `clientes` não
    existir mais com esse nome (a migração termina renomeando-a para
    `clientes_legado`). Repare que não dá pra usar "a tabela `usuarios` já
    existe" como guarda: o `create_all` chamado logo antes (em `init_db`) já
    cria `usuarios`/`empresas` vazias no primeiro startup, então essa tabela
    sempre existe por aqui. Se `clientes` não existe (nem `clientes_legado`),
    é um banco novo — `create_all` já criou tudo do jeito certo.
    """
    inspector = inspect(engine)
    tabelas = set(inspector.get_table_names())

    if "clientes" not in tabelas:
        return  # já migrado (clientes virou clientes_legado) ou banco novo

    with engine.begin() as conn:
        clientes = conn.execute(
            text("SELECT id, nome_empresa, email, senha_hash, role, criado_em FROM clientes")
        ).mappings().all()

        for c in clientes:
            # O SQLAlchemy Enum antigo persistia o *nome* do membro Python
            # ("cliente"/"super_admin"), não o `.value` — mesma observação já
            # documentada na migração anterior (_migrar_coluna_role).
            eh_super_admin = c["role"] == "super_admin"

            if eh_super_admin:
                empresa_id = None
            else:
                # Preserva o id original: cliente.id vira empresa.id, o que
                # torna o rename de coluna cliente_id -> empresa_id um simples
                # ALTER TABLE (sem precisar remapear FKs linha a linha).
                # `pending_payment`, não `active`: preserva a mesma trava de pagamento de
                # qualquer cadastro novo — a empresa migrada do esquema antigo só recupera
                # acesso completando o checkout da Stripe (ver routes.signup e
                # auth.garantir_assinatura_ativa), exatamente como qualquer conta nova.
                conn.execute(
                    text(
                        "INSERT INTO empresas "
                        "(id, nome_empresa, criado_em, status_assinatura) "
                        "VALUES (:id, :nome_empresa, :criado_em, 'pending_payment')"
                    ),
                    {
                        "id": c["id"],
                        "nome_empresa": c["nome_empresa"],
                        "criado_em": c["criado_em"],
                    },
                )
                empresa_id = c["id"]

            conn.execute(
                text(
                    "INSERT INTO usuarios "
                    "(id, empresa_id, nome, email, senha_hash, role, criado_em) "
                    "VALUES (:id, :empresa_id, :nome, :email, :senha_hash, :role, :criado_em)"
                ),
                {
                    "id": c["id"],
                    "empresa_id": empresa_id,
                    "nome": None,
                    "email": c["email"],
                    "senha_hash": c["senha_hash"],
                    # Nome do membro Python (não o .value) — mesma convenção de
                    # persistência do SQLAlchemy Enum usada acima para `clientes.role`.
                    "role": "super_admin" if eh_super_admin else "admin",
                    "criado_em": c["criado_em"],
                },
            )

        for tabela in ("cameras", "metricas_atendimento", "metricas_ocupacao"):
            colunas = {col["name"] for col in inspector.get_columns(tabela)}
            if "cliente_id" in colunas and "empresa_id" not in colunas:
                conn.execute(text(f"ALTER TABLE {tabela} RENAME COLUMN cliente_id TO empresa_id"))

        conn.execute(text("ALTER TABLE clientes RENAME TO clientes_legado"))

    print(
        f"[migração] {len(clientes)} conta(s) do esquema antigo migradas para "
        "empresas/usuarios (tabela `clientes` preservada como `clientes_legado`)."
    )


def _migrar_enum_status_assinatura() -> None:
    """
    Adiciona o label `pending_payment` (novo estado inicial de toda empresa
    cadastrada — ver models.StatusAssinatura e routes.signup) ao tipo ENUM
    nativo do Postgres, caso ainda não exista.

    `Base.metadata.create_all` só cria o tipo ENUM na primeira vez — rodando
    de novo num banco que já tem `statusassinatura` criado (qualquer deploy
    depois do primeiro) ele não adiciona labels novos ao enum do Python, e um
    INSERT/UPDATE com 'pending_payment' falharia em produção sem isso. SQLite
    (dev local) não tem ENUM nativo (a checagem de valores vira um simples
    CHECK constraint recriado do zero a cada `create_all` em banco novo), então
    não precisa dessa migração — só apague `backend/saas_cameras.db` se seu
    banco local for de antes dessa mudança.

    `ALTER TYPE ... ADD VALUE` não pode rodar dentro de uma transação em
    versões antigas do Postgres, por isso a conexão AUTOCOMMIT dedicada.
    """
    if not DATABASE_URL.startswith("postgresql"):
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ALTER TYPE statusassinatura ADD VALUE IF NOT EXISTS 'pending_payment'"))


def _migrar_colunas_fila() -> None:
    """
    Adiciona à tabela `metricas_atendimento`, já existente em qualquer deploy
    anterior ao Dashboard Analytics Tópico 1, as colunas `tempo_espera_segundos`
    e `desistiu` (ver models.MetricaAtendimento). `create_all` só cria tabelas
    que ainda não existem — numa tabela pré-existente é preciso ALTER TABLE
    explícito, mesmo padrão de `_migrar_para_multi_tenant` acima.
    """
    inspector = inspect(engine)
    if "metricas_atendimento" not in inspector.get_table_names():
        return  # banco novo: create_all já criou a tabela com as colunas certas

    colunas = {col["name"] for col in inspector.get_columns("metricas_atendimento")}
    with engine.begin() as conn:
        if "tempo_espera_segundos" not in colunas:
            conn.execute(text("ALTER TABLE metricas_atendimento ADD COLUMN tempo_espera_segundos FLOAT"))
        if "desistiu" not in colunas:
            # Boolean DEFAULT literal difere por dialeto (Postgres não aceita 0/1
            # implícito para uma coluna BOOLEAN) — mesma ressalva já documentada
            # em `_migrar_enum_status_assinatura` para diferenças Postgres/SQLite.
            default = "FALSE" if DATABASE_URL.startswith("postgresql") else "0"
            conn.execute(
                text(f"ALTER TABLE metricas_atendimento ADD COLUMN desistiu BOOLEAN NOT NULL DEFAULT {default}")
            )


def init_db() -> None:
    """Cria todas as tabelas no banco (se não existirem) e aplica migrações pendentes."""
    import models  # noqa: F401  garante que os modelos estejam registrados no Base antes do create_all

    Base.metadata.create_all(bind=engine)
    _migrar_enum_status_assinatura()
    _migrar_para_multi_tenant()
    _migrar_colunas_fila()


def seed_super_admin() -> None:
    """Garante que sempre exista pelo menos uma conta SUPER_ADMIN (bootstrap)."""
    import models
    from auth import hash_password
    from config import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD

    db = SessionLocal()
    try:
        ja_existe = (
            db.query(models.Usuario).filter(models.Usuario.role == models.RoleUsuario.super_admin).first()
        )
        if ja_existe:
            return

        admin = models.Usuario(
            empresa_id=None,
            nome="Administrador",
            email=SUPER_ADMIN_EMAIL.strip().lower(),
            senha_hash=hash_password(SUPER_ADMIN_PASSWORD),
            role=models.RoleUsuario.super_admin,
        )
        db.add(admin)
        db.commit()
        print(
            f"[bootstrap] Conta SUPER_ADMIN criada: {SUPER_ADMIN_EMAIL} "
            "(senha definida em SUPER_ADMIN_PASSWORD — troque em produção)"
        )
    finally:
        db.close()
