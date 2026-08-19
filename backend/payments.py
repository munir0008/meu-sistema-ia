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


def criar_portal_session(empresa: "models.Empresa") -> str:
    _exigir_configurado()
    if not empresa.stripe_customer_id:
        raise StripeNaoConfigurado("Esta empresa ainda não tem uma assinatura Stripe iniciada.")

    session = stripe.billing_portal.Session.create(
        customer=empresa.stripe_customer_id,
        return_url=f"{FRONTEND_URL}/assinatura",
    )
    return session.url


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
