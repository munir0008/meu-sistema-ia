"""
E-mails transacionais via Resend (https://resend.com — API simples, sem SMTP,
com plano gratuito generoso; é o que este módulo usa por padrão).

Sem RESEND_API_KEY configurada, todo envio é pulado (logado no console) — o
cadastro e o processamento do webhook da Stripe NUNCA falham por causa de
e-mail: as funções aqui sempre capturam exceções e devolvem True/False em vez
de propagar erro.
"""
import logging
from typing import TYPE_CHECKING, Optional

import resend

from config import EMAIL_FROM, FRONTEND_URL, RESEND_API_KEY

if TYPE_CHECKING:
    import models

logger = logging.getLogger("emails")

resend.api_key = RESEND_API_KEY

_COR_PRIMARIA = "#0f172a"
_COR_DESTAQUE = "#06b6d4"


def _layout_email(titulo: str, corpo_html: str, texto_botao: Optional[str] = None, url_botao: Optional[str] = None) -> str:
    """Casca HTML mínima e responsiva reaproveitada por todo e-mail transacional."""
    botao_html = (
        f"""
        <tr>
          <td style="padding-top:24px;">
            <a href="{url_botao}" style="display:inline-block;background:{_COR_DESTAQUE};color:#052e33;
              font-weight:600;font-size:14px;padding:12px 22px;border-radius:8px;text-decoration:none;">
              {texto_botao}
            </a>
          </td>
        </tr>
        """
        if texto_botao and url_botao
        else ""
    )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      style="background:#f4f4f5;padding:32px 0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
            style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e4e4e7;">
            <tr>
              <td style="background:{_COR_PRIMARIA};padding:20px 28px;">
                <span style="color:#ffffff;font-size:15px;font-weight:600;">VisionSaaS</span>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <h1 style="margin:0 0 12px;font-size:18px;color:#18181b;">{titulo}</h1>
                <div style="font-size:14px;line-height:1.6;color:#3f3f46;">{corpo_html}</div>
                <table role="presentation">{botao_html}</table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;background:#fafafa;border-top:1px solid #e4e4e7;">
                <span style="font-size:11px;color:#a1a1aa;">
                  Você está recebendo este e-mail porque uma conta foi criada na VisionSaaS com este endereço.
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """


def _enviar(destinatario: str, assunto: str, html: str) -> bool:
    if not RESEND_API_KEY:
        logger.info("[emails] RESEND_API_KEY não configurada — pulando envio de %r para %s", assunto, destinatario)
        return False
    try:
        resend.Emails.send({"from": EMAIL_FROM, "to": [destinatario], "subject": assunto, "html": html})
        return True
    except Exception:
        logger.exception("[emails] falha ao enviar %r para %s", assunto, destinatario)
        return False


def enviar_email_boas_vindas(destinatario: str, nome_admin: Optional[str], empresa: "models.Empresa") -> bool:
    """
    Disparado logo após o autocadastro em POST /api/auth/signup — nesse ponto
    a conta ainda está com status `pending_payment` (o frontend já redirecionou
    o navegador para o Stripe Checkout nesse meio-tempo). O link deste e-mail
    aponta para /login, não /dashboard: não existe sessão automática após o
    cadastro, e as rotas de negócio continuam bloqueadas até o pagamento ser
    confirmado (ver auth.garantir_assinatura_ativa).
    """
    saudacao = f"Olá, {nome_admin}!" if nome_admin else "Olá!"
    corpo = f"""
      <p>{saudacao}</p>
      <p>A conta da <strong>{empresa.nome_empresa}</strong> foi criada com sucesso na VisionSaaS.
      Para ativar o acesso e começar a monitorar suas câmeras, finalize o pagamento da assinatura
      pelo link que abrimos para você no checkout. Se fechou a página antes de concluir, é só
      entrar na sua conta abaixo — a gente leva você direto para retomar o pagamento.</p>
    """
    html = _layout_email("Bem-vindo(a) à VisionSaaS 🎥", corpo, "Entrar na minha conta", f"{FRONTEND_URL}/login")
    return _enviar(destinatario, "Bem-vindo(a) à VisionSaaS", html)


def enviar_email_assinatura_confirmada(destinatario: str, nome_admin: Optional[str], empresa: "models.Empresa") -> bool:
    """Disparado pelo webhook da Stripe (checkout.session.completed) — ver payments.py."""
    saudacao = f"Olá, {nome_admin}!" if nome_admin else "Olá!"
    corpo = f"""
      <p>{saudacao}</p>
      <p>Recebemos a confirmação de pagamento da <strong>{empresa.nome_empresa}</strong> — sua
      assinatura do Plano Completo está ativa. Obrigado por continuar com a gente!</p>
      <p>Você pode gerenciar forma de pagamento e faturas a qualquer momento na página de
      Assinatura do seu painel.</p>
    """
    html = _layout_email("Assinatura confirmada ✅", corpo, "Ver minha assinatura", f"{FRONTEND_URL}/assinatura")
    return _enviar(destinatario, "Sua assinatura VisionSaaS está ativa", html)
