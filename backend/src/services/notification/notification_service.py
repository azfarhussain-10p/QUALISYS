"""
QUALISYS — NotificationService (Email)
Story: 1-1-user-account-creation — send_verification_email
Story: 1-3-team-member-invitation — send_invitation_email (AC3)

Dual-provider: SendGrid (primary) → SES (fallback).
In development (MailCatcher): sends to SMTP localhost:1025.
Jinja2 template rendering — src/templates/email/
"""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import get_settings
from src.logger import logger

settings = get_settings()

# Jinja2 template loader
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "email"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


async def send_verification_email(
    recipient_email: str,
    full_name: str,
    verification_token: str,
    correlation_id: str,
) -> None:
    """
    Send branded email verification link to new user.
    Token is embedded in URL; link sets email_verified=true on click.

    AC3: signed JWT token with 24-hour expiry.
    """
    verification_url = (
        f"{settings.frontend_url}/verify-email?token={verification_token}"
    )

    html_body = _render_template(
        "verification.html",
        full_name=full_name,
        verification_url=verification_url,
        app_name="QUALISYS",
    )
    text_body = (
        f"Hi {full_name},\n\n"
        f"Please verify your email address by visiting:\n{verification_url}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"If you did not sign up, please ignore this email.\n"
    )

    subject = "Verify your QUALISYS account"

    await _send_email(
        recipient_email=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        correlation_id=correlation_id,
    )


async def _send_email(
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    correlation_id: str,
) -> None:
    """
    Dispatch email via SendGrid (primary) or SMTP dev relay (MailCatcher).
    SES fallback is wired in Story 1.5 when full dual-provider setup is done.
    """
    if settings.sendgrid_api_key:
        await _send_via_sendgrid(
            recipient_email, subject, html_body, text_body, correlation_id
        )
    else:
        await _send_via_smtp(
            recipient_email, subject, html_body, text_body, correlation_id
        )


async def _send_via_sendgrid(
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    correlation_id: str,
) -> None:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Content, Mail, To

        sg = SendGridAPIClient(api_key=settings.sendgrid_api_key)
        message = Mail(
            from_email=(settings.from_email, settings.from_name),
            to_emails=To(recipient_email),
            subject=subject,
        )
        message.add_content(Content("text/plain", text_body))
        message.add_content(Content("text/html", html_body))

        response = sg.client.mail.send.post(request_body=message.get())
        logger.info(
            "Verification email sent via SendGrid",
            status_code=response.status_code,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.error(
            "SendGrid email delivery failed — falling back to SMTP",
            exc=exc,
            correlation_id=correlation_id,
        )
        await _send_via_smtp(
            recipient_email, subject, html_body, text_body, correlation_id
        )


async def _send_via_smtp(
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    correlation_id: str,
) -> None:
    """SMTP relay — used for MailCatcher in local dev (AC from Story 0-21).

    smtplib is synchronous; wrapped in asyncio.to_thread to avoid blocking the
    event loop (code-review finding M1).
    """
    import asyncio
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.from_name} <{settings.from_email}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        raw_message = msg.as_string()
        smtp_host = settings.smtp_host
        smtp_port = settings.smtp_port
        from_email = settings.from_email

        def _blocking_send() -> None:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.sendmail(from_email, [recipient_email], raw_message)

        await asyncio.to_thread(_blocking_send)

        logger.info(
            "Verification email sent via SMTP",
            host=settings.smtp_host,
            port=settings.smtp_port,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.error(
            "SMTP email delivery failed",
            exc=exc,
            correlation_id=correlation_id,
        )
        raise


async def send_invitation_email(
    recipient_email: str,
    inviter_name: str,
    org_name: str,
    role: str,
    invite_token: str,
    expires_at,
    correlation_id: str,
) -> None:
    """
    Send branded invitation email via SendGrid/SES with retry logic.
    Story: 1-3-team-member-invitation, AC3.

    AC3: async, non-blocking, 3 retry attempts with exponential backoff (1s, 4s, 16s).
    AC3: mobile-responsive HTML template, includes inviter name, org name, role, CTA, expiry.
    """
    import asyncio

    accept_url = f"{settings.frontend_url}/invite/accept?token={invite_token}"
    expiry_date = expires_at.strftime("%B %d, %Y") if hasattr(expires_at, "strftime") else str(expires_at)

    html_body = _render_template(
        "invitation.html",
        app_name="QUALISYS",
        inviter_name=inviter_name,
        org_name=org_name,
        role=role,
        accept_url=accept_url,
        expiry_date=expiry_date,
    )
    text_body = (
        f"Hi,\n\n"
        f"{inviter_name} has invited you to join {org_name} on QUALISYS.\n\n"
        f"Role: {role}\n"
        f"Expires: {expiry_date}\n\n"
        f"Accept your invitation:\n{accept_url}\n\n"
        f"If you were not expecting this invitation, you can safely ignore this email.\n"
    )
    subject = f"You've been invited to join {org_name} on QUALISYS"

    # AC3: retry up to 3 attempts with exponential backoff (1s, 4s, 16s)
    for attempt in range(1, 4):
        try:
            await _send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                correlation_id=correlation_id,
            )
            logger.info(
                "Invitation email sent",
                recipient=recipient_email,
                org=org_name,
                attempt=attempt,
                correlation_id=correlation_id,
            )
            return
        except Exception as exc:
            if attempt < 3:
                backoff = 4 ** (attempt - 1)  # 1s, 4s, 16s
                logger.warning(
                    "Invitation email delivery failed, retrying",
                    attempt=attempt,
                    backoff_seconds=backoff,
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "Invitation email delivery failed after 3 attempts",
                    recipient=recipient_email,
                    error=str(exc),
                    correlation_id=correlation_id,
                )


async def send_role_changed_email(
    recipient_email: str,
    full_name: str,
    org_name: str,
    old_role: str,
    new_role: str,
    correlation_id: str,
) -> None:
    """
    Notify a member that their role has been changed. AC4 (Story 1.4).
    Sent asynchronously — delivery failure logged, does not fail the API call.
    """
    html_body = _render_template(
        "role-changed.html",
        app_name="QUALISYS",
        full_name=full_name,
        org_name=org_name,
        old_role=old_role,
        new_role=new_role,
    )
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your role in {org_name} on QUALISYS has been updated.\n\n"
        f"Previous role: {old_role}\n"
        f"New role: {new_role}\n\n"
        f"This change is effective immediately.\n\n"
        f"If you did not expect this change, please contact your organization admin.\n"
    )
    subject = f"Your role in {org_name} has been updated"

    try:
        await _send_email(
            recipient_email=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            correlation_id=correlation_id,
        )
        logger.info(
            "Role-changed email sent",
            recipient=recipient_email,
            org=org_name,
            new_role=new_role,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.error(
            "Role-changed email delivery failed (non-fatal)",
            recipient=recipient_email,
            error=str(exc),
            correlation_id=correlation_id,
        )


async def send_member_removed_email(
    recipient_email: str,
    full_name: str,
    org_name: str,
    correlation_id: str,
) -> None:
    """
    Notify a removed member that their access has been revoked. AC4 (Story 1.4).
    Sent asynchronously — delivery failure logged, does not fail the API call.
    """
    html_body = _render_template(
        "member-removed.html",
        app_name="QUALISYS",
        full_name=full_name,
        org_name=org_name,
    )
    text_body = (
        f"Hi {full_name},\n\n"
        f"You have been removed from {org_name} on QUALISYS.\n\n"
        f"Your access to all projects in this organization has been revoked.\n\n"
        f"If you believe this is a mistake, please contact your organization admin.\n"
    )
    subject = f"Your access to {org_name} has been revoked"

    try:
        await _send_email(
            recipient_email=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            correlation_id=correlation_id,
        )
        logger.info(
            "Member-removed email sent",
            recipient=recipient_email,
            org=org_name,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.error(
            "Member-removed email delivery failed (non-fatal)",
            recipient=recipient_email,
            error=str(exc),
            correlation_id=correlation_id,
        )


def _render_template(template_name: str, **context) -> str:
    template = _jinja_env.get_template(template_name)
    return template.render(**context)
