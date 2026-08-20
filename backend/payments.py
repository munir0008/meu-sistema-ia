"""
Integração com Stripe (Checkout + Customer Portal + Webhook).

Lógica pura de billing, sem depender do FastAPI — mesmo espírito de
`reports.py` (coleta/gera, quem expõe como endpoint é `routes.py`). Todo
`stripe.*` fica isolado aqui para o resto do backend nunca importar o SDK
diretamente.

Sem chaves configuradas (STRIPE_SECRET_KEY vazio no .env — cenário padrão até
o usuário preencher as chaves de teste), as funções levantam `StripeNaoConfigurado`
em vez de deixar o SDK estourar um erro genérico.
"""
import logging
from datetime import datetime
from typing import Optional

import stripe
from sqlalchemy.orm import Session

import emails
import models
from config import (
    FRONTEND_URL,
    STRIPE_PRICE_ID_UNICO,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)

logger = logging.getLogger("payments")

stripe.api_key = STRIPE_SECRET_KEY

# Plataforma vende um único plano recorrente — ver STRIPE_PRICE_ID_UNICO no .env.
PRECOS_POR_PLANO = {
    models.PlanoAssinatura.completo: STRIPE_PRICE_ID_UNICO,
}

# Mapeia o `status` de uma Subscription da Stripe para o nosso enum StatusAssinatura.
_MAPA_STATUS_STRIPE = {
    "trialing": models.StatusAssinatura.trial,
    "active": models.StatusAssinatura.active,
    "past_due": models.StatusAssinatura.past_due,
    "canceled": models.StatusAssinatura.canceled,
    "unpaid": models.StatusAssinatura.unpaid,
    "incomplete": models.StatusAssinatura.unpaid,
    "incomplete_expired": models.StatusAssinatura.canceled,
}


class StripeNaoConfigurado(Exception):
    """Levantada quando STRIPE_SECRET_KEY (ou o price ID do plano) ainda não foi definido."""


def _exigir_configurado() -> None:
    if not STRIPE_SECRET_KEY:
        raise StripeNaoConfigurado(
            "STRIPE_SECRET_KEY não configurada no .env — preencha as chaves de teste da Stripe."
        )


def _price_id_do_plano(plano: "models.PlanoAssinatura") -> str:
    price_id = PRECOS_POR_PLANO.get(plano)
    if not price_id:
        raise StripeNaoConfigurado(
            "STRIPE_PRICE_ID_UNICO não configurado no .env — crie o produto/preço "
            "no Dashboard da Stripe e cole o price ID lá."
        )
    return price_id


def obter_ou_criar_customer(db: Session, empresa: "models.Empresa", email_admin: str) -> str:
    """Reaproveita o `stripe_customer_id` salvo, ou cria um Customer novo na Stripe."""
    _exigir_configurado()
    if empresa.stripe_customer_id:
        return empresa.stripe_customer_id

    customer = stripe.Customer.create(
        name=empresa.nome_empresa,
        email=email_admin,
        metadata={"empresa_id": str(empresa.id)},
    )
    empresa.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def criar_checkout_session(db: Session, empresa: "models.Empresa", plano: "models.PlanoAssinatura", email_admin: str) -> str:
    _exigir_configurado()
    price_id = _price_id_do_plano(plano)
    customer_id = obter_ou_criar_customer(db, empresa, email_admin)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{FRONTEND_URL}/assinatura?checkout=sucesso",
        cancel_url=f"{FRONTEND_URL}/assinatura?checkout=cancelado",
        metadata={"empresa_id": str(empresa.id), "plano": plano.value},
        subscription_data={"metadata": {"empresa_id": str(empresa.id), "plano": plano.value}},
    )
    return session.url


def criar_portal_ou_checkout_session(
    db: Session, empresa: "models.Empresa", email_admin: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Gera a URL do Customer Portal para a empresa gerenciar a assinatura
    existente. Se ela ainda não tiver um `stripe_customer_id` válido — nunca
    chegou a pagar, ou o customer salvo não existe mais na Stripe (ambiente
    de chaves trocado, customer removido no Dashboard etc.) — não estoura
    erro: cai para uma nova Checkout Session do plano único, para o ADMIN
    poder fazer o primeiro pagamento em vez de ver "portal indisponível".

    Retorna (portal_url, checkout_url) — sempre exatamente um dos dois vem
    preenchido; o outro fica None.
    """
    _exigir_configurado()

    logger.info(
        "customer-portal: empresa_id=%s tem stripe_customer_id=%r",
        empresa.id, empresa.stripe_customer_id,
    )

    try:
        if empresa.stripe_customer_id:
            try:
                session = stripe.billing_portal.Session.create(
                    customer=empresa.stripe_customer_id,
                    return_url=f"{FRONTEND_URL}/assinatura",
                )
                logger.info(
                    "customer-portal: portal session criada OK para empresa_id=%s", empresa.id
                )
                return session.url, None
            except stripe.error.InvalidRequestError as exc:
                # customer_id salvo não existe mais nessa conta/ambiente Stripe —
                # trata como se a empresa nunca tivesse um customer.
                logger.warning(
                    "customer-portal: stripe_customer_id=%s inválido para empresa_id=%s "
                    "(http_status=%s code=%s): %s — caindo para checkout de 1º pagamento",
                    empresa.stripe_customer_id, empresa.id,
                    getattr(exc, "http_status", None), getattr(exc, "code", None),
                    exc.user_message or str(exc),
                )
                empresa.stripe_customer_id = None
            except stripe.error.StripeError as exc:
                # Qualquer outro erro da Stripe (auth, permissão, rede, rate limit...)
                # não tem fallback óbvio — loga com o máximo de detalhe e propaga.
                logger.exception(
                    "customer-portal: erro Stripe %s ao abrir portal p/ empresa_id=%s "
                    "(http_status=%s code=%s request_id=%s)",
                    type(exc).__name__, empresa.id,
                    getattr(exc, "http_status", None), getattr(exc, "code", None),
                    getattr(exc, "request_id", None),
                )
                raise

        plano = empresa.plano_atual or models.PlanoAssinatura.completo
        logger.info(
            "customer-portal: sem customer válido — criando checkout de 1º pagamento "
            "p/ empresa_id=%s plano=%s",
            empresa.id, plano,
        )
        checkout_url = criar_checkout_session(db, empresa, plano, email_admin)
        return None, checkout_url
    except StripeNaoConfigurado:
        raise
    except Exception:
        # Pega qualquer coisa que não seja Stripe (erro de banco no commit, etc.)
        # que de outra forma viraria um 500 "Internal Server Error" sem corpo
        # JSON — o que faz o frontend perder o `detail` e cair na mensagem
        # genérica. Loga com traceback completo pra aparecer no Render.
        logger.exception(
            "customer-portal: falha inesperada (não-Stripe) para empresa_id=%s", empresa.id
        )
        raise


def construir_evento_webhook(payload: bytes, assinatura: Optional[str]) -> "stripe.Event":
    """Valida a assinatura do webhook (STRIPE_WEBHOOK_SECRET) e devolve o Event já verificado."""
    _exigir_configurado()
    if not STRIPE_WEBHOOK_SECRET:
        raise StripeNaoConfigurado("STRIPE_WEBHOOK_SECRET não configurado no .env.")
    return stripe.Webhook.construct_event(payload, assinatura, STRIPE_WEBHOOK_SECRET)


def _empresa_por_customer_id(db: Session, customer_id: str) -> Optional["models.Empresa"]:
    return db.query(models.Empresa).filter(models.Empresa.stripe_customer_id == customer_id).first()


def _admin_da_empresa(db: Session, empresa: "models.Empresa") -> Optional["models.Usuario"]:
    """E-mail de confirmação de assinatura vai para o ADMIN mais antigo da empresa."""
    return (
        db.query(models.Usuario)
        .filter(models.Usuario.empresa_id == empresa.id, models.Usuario.role == models.RoleUsuario.admin)
        .order_by(models.Usuario.id)
        .first()
    )


def _timestamp_para_datetime(ts: Optional[int]) -> Optional[datetime]:
    return datetime.utcfromtimestamp(ts) if ts else None


def _plano_da_subscription(subscription: dict) -> Optional["models.PlanoAssinatura"]:
    plano_meta = (subscription.get("metadata") or {}).get("plano")
    if plano_meta:
        try:
            return models.PlanoAssinatura(plano_meta)
        except ValueError:
            pass
    # Fallback: identifica o plano pelo price ID do primeiro item da assinatura.
    itens = (subscription.get("items") or {}).get("data") or []
    price_id = itens[0]["price"]["id"] if itens else None
    for plano, pid in PRECOS_POR_PLANO.items():
        if pid and pid == price_id:
            return plano
    return None


def _aplicar_dados_subscription(empresa: "models.Empresa", subscription: dict) -> None:
    empresa.stripe_subscription_id = subscription.get("id")
    status_stripe = subscription.get("status")
    empresa.status_assinatura = _MAPA_STATUS_STRIPE.get(status_stripe, models.StatusAssinatura.active)
    plano = _plano_da_subscription(subscription)
    if plano:
        empresa.plano_atual = plano
    empresa.data_fim_periodo = _timestamp_para_datetime(subscription.get("current_period_end"))


def processar_evento_webhook(db: Session, event: "stripe.Event") -> None:
    """
    Trata os eventos relevantes de assinatura. Busca a empresa sempre pelo
    `stripe_customer_id` (mais estável do que confiar só nos metadados).
    """
    tipo = event["type"]
    obj = event["data"]["object"]

    if tipo == "checkout.session.completed":
        empresa_id = (obj.get("metadata") or {}).get("empresa_id")
        customer_id = obj.get("customer")
        empresa = (
            db.get(models.Empresa, int(empresa_id))
            if empresa_id
            else _empresa_por_customer_id(db, customer_id)
        )
        if not empresa:
            return
        empresa.stripe_customer_id = customer_id
        subscription_id = obj.get("subscription")
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            _aplicar_dados_subscription(empresa, subscription)
        db.commit()

        admin = _admin_da_empresa(db, empresa)
        if admin:
            emails.enviar_email_assinatura_confirmada(admin.email, admin.nome, empresa)

    elif tipo in ("customer.subscription.updated", "customer.subscription.created"):
        empresa = _empresa_por_customer_id(db, obj.get("customer"))
        if not empresa:
            return
        _aplicar_dados_subscription(empresa, obj)
        db.commit()

    elif tipo == "customer.subscription.deleted":
        empresa = _empresa_por_customer_id(db, obj.get("customer"))
        if not empresa:
            return
        empresa.status_assinatura = models.StatusAssinatura.canceled
        db.commit()
