"""Async email delivery via stdlib smtplib (runs in a thread to stay non-blocking).

Usage:
    await send_password_reset_email(to_email, display_name, reset_link)

SMTP is configured through environment variables (see app/config.py):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS

When SMTP_HOST is not set, emails are logged at WARNING level and skipped —
useful for local dev without a mail server.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from textwrap import dedent

from app.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Internal SMTP sender (runs synchronously in a thread)                       #
# --------------------------------------------------------------------------- #

def _smtp_send(to: str, subject: str, html: str, plain: str) -> None:
    """Blocking SMTP send — call via asyncio.to_thread."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to

    if plain:
        msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        if settings.smtp_port == 465 or not settings.smtp_tls:
            # Implicit TLS (SMTP_SSL)
            with smtplib.SMTP_SSL(
                settings.smtp_host,  # type: ignore[arg-type]
                settings.smtp_port,
                context=ctx,
                timeout=15,
            ) as smtp:
                if settings.smtp_user and settings.smtp_password:
                    # Strip spaces — Gmail App Passwords are displayed with spaces
                    # but the SMTP server expects them without
                    smtp.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
                smtp.send_message(msg)
        else:
            # STARTTLS (most common for port 587)
            with smtplib.SMTP(
                settings.smtp_host,  # type: ignore[arg-type]
                settings.smtp_port,
                timeout=15,
            ) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ctx)
                smtp.ehlo()
                if settings.smtp_user and settings.smtp_password:
                    # Strip spaces — Gmail App Passwords are displayed with spaces
                    # but the SMTP server expects them without
                    smtp.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
                smtp.send_message(msg)

        logger.info("Email sent to=%s subject=%r", to, subject)

    except Exception:
        logger.exception("SMTP delivery failed to=%s subject=%r", to, subject)
        raise


async def _send(to: str, subject: str, html: str, plain: str = "") -> None:
    """Top-level async send — skips silently when SMTP is unconfigured."""
    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured — skipping email to=%s subject=%r. "
            "Set SMTP_HOST / SMTP_USER / SMTP_PASSWORD in .env to enable real emails.",
            to,
            subject,
        )
        return
    if not settings.smtp_user or not settings.smtp_password:
        logger.error(
            "SMTP_HOST is set but SMTP_USER or SMTP_PASSWORD is missing — "
            "cannot authenticate. Check your .env file."
        )
        return
    try:
        await asyncio.to_thread(_smtp_send, to, subject, html, plain)
    except Exception:
        logger.exception(
            "SMTP send failed to=%s subject=%r — check SMTP credentials and network access.",
            to,
            subject,
        )
        raise


# --------------------------------------------------------------------------- #
# Public helpers                                                               #
# --------------------------------------------------------------------------- #

async def send_password_reset_email(
    to_email: str,
    display_name: str,
    reset_link: str,
) -> None:
    """Send the password-reset email with a one-hour expiry link."""
    subject = "Reset your Neo-Kanban password"

    html = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
        <body style="margin:0;padding:0;background:#f8fafc;font-family:'IBM Plex Sans',Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 16px;">
            <tr><td align="center">
              <table width="100%" style="max-width:520px;background:#ffffff;border-radius:12px;
                     border:1px solid #e2e8f0;overflow:hidden;">
                <!-- Header -->
                <tr>
                  <td style="background:linear-gradient(135deg,#0f3530 0%,#0f766e 100%);
                             padding:28px 32px;text-align:center;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:20px;
                                 font-weight:700;color:#ecfeff;letter-spacing:-0.02em;">
                      Neo<span style="color:#5eead4;">Kanban</span>
                    </span>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:32px;">
                    <p style="margin:0 0 8px;font-size:18px;font-weight:600;color:#0f172a;">
                      Hi {display_name},
                    </p>
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#475569;">
                      We received a request to reset the password for your Neo-Kanban account.
                      Click the button below to choose a new password.
                      This link expires in <strong>1 hour</strong>.
                    </p>
                    <table cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td align="center">
                          <a href="{reset_link}"
                             style="display:inline-block;padding:14px 32px;
                                    background:linear-gradient(135deg,#f97316,#ea580c);
                                    color:#ffffff;font-size:15px;font-weight:600;
                                    text-decoration:none;border-radius:10px;
                                    box-shadow:0 4px 12px -4px rgba(249,115,22,.55);">
                            Reset password
                          </a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:24px 0 0;font-size:12.5px;color:#94a3b8;line-height:1.5;">
                      If you didn&rsquo;t request a password reset, you can safely ignore this email.
                      Your password will not change.<br><br>
                      Or copy this link into your browser:<br>
                      <a href="{reset_link}" style="color:#0f766e;word-break:break-all;">
                        {reset_link}
                      </a>
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="padding:16px 32px;border-top:1px solid #f1f5f9;
                             text-align:center;font-size:11px;color:#94a3b8;">
                    &copy; 2026 Neo-Kanban &mdash; AI-Agentic Project Management
                  </td>
                </tr>
              </table>
            </td></tr>
          </table>
        </body>
        </html>
    """)

    plain = dedent(f"""\
        Hi {display_name},

        We received a request to reset the password for your Neo-Kanban account.

        Click the link below to reset your password (expires in 1 hour):
        {reset_link}

        If you didn't request a password reset, you can safely ignore this email.

        — Neo-Kanban Team
    """)

    await _send(to_email, subject, html, plain)


async def send_verification_otp_email(
    to_email: str,
    display_name: str,
    otp_code: str,
) -> None:
    """Send a 6-digit OTP verification email during registration."""
    subject = "Your Neo-Kanban verification code"

    html = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
        <body style="margin:0;padding:0;background:#f8fafc;font-family:'IBM Plex Sans',Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 16px;">
            <tr><td align="center">
              <table width="100%" style="max-width:520px;background:#ffffff;border-radius:12px;
                     border:1px solid #e2e8f0;overflow:hidden;">
                <!-- Header -->
                <tr>
                  <td style="background:linear-gradient(135deg,#0f3530 0%,#0f766e 100%);
                             padding:28px 32px;text-align:center;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:20px;
                                 font-weight:700;color:#ecfeff;letter-spacing:-0.02em;">
                      Neo<span style="color:#5eead4;">Kanban</span>
                    </span>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:32px;">
                    <p style="margin:0 0 8px;font-size:18px;font-weight:600;color:#0f172a;">
                      Hi {display_name},
                    </p>
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#475569;">
                      Enter the verification code below to complete your registration.
                      This code expires in <strong>10 minutes</strong>.
                    </p>
                    <!-- OTP Box -->
                    <table cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td align="center" style="padding:8px 0 28px;">
                          <div style="display:inline-block;background:#f0fdf4;border:2px solid #86efac;
                                      border-radius:12px;padding:18px 40px;">
                            <span style="font-family:'JetBrains Mono',monospace;font-size:36px;
                                         font-weight:800;letter-spacing:0.18em;color:#15803d;">
                              {otp_code}
                            </span>
                          </div>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:12.5px;color:#94a3b8;line-height:1.5;text-align:center;">
                      If you didn&rsquo;t request this, you can safely ignore this email.
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="padding:16px 32px;border-top:1px solid #f1f5f9;
                             text-align:center;font-size:11px;color:#94a3b8;">
                    &copy; 2026 Neo-Kanban &mdash; AI-Agentic Project Management
                  </td>
                </tr>
              </table>
            </td></tr>
          </table>
        </body>
        </html>
    """)

    plain = dedent(f"""\
        Hi {display_name},

        Your Neo-Kanban verification code is:

            {otp_code}

        This code expires in 10 minutes.

        If you didn't request this, ignore this email.

        — Neo-Kanban Team
    """)

    await _send(to_email, subject, html, plain)


async def send_password_reset_otp_email(
    to_email: str,
    display_name: str,
    otp_code: str,
) -> None:
    """Send a 6-digit OTP for password reset."""
    subject = "Mã xác nhận đặt lại mật khẩu Neo-Kanban"

    html = dedent(f"""\
        <!DOCTYPE html>
        <html lang="vi">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
        <body style="margin:0;padding:0;background:#f8fafc;font-family:'IBM Plex Sans',Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 16px;">
            <tr><td align="center">
              <table width="100%" style="max-width:520px;background:#ffffff;border-radius:12px;
                     border:1px solid #e2e8f0;overflow:hidden;">
                <!-- Header -->
                <tr>
                  <td style="background:linear-gradient(135deg,#0f3530 0%,#0f766e 100%);
                             padding:28px 32px;text-align:center;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:20px;
                                 font-weight:700;color:#ecfeff;letter-spacing:-0.02em;">
                      Neo<span style="color:#5eead4;">Kanban</span>
                    </span>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:32px;">
                    <p style="margin:0 0 8px;font-size:18px;font-weight:600;color:#0f172a;">
                      Xin chào {display_name},
                    </p>
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#475569;">
                      Bạn vừa yêu cầu đặt lại mật khẩu. Nhập mã bên dưới để tiếp tục.
                      Mã có hiệu lực trong <strong>10 phút</strong>.
                    </p>
                    <!-- OTP Box -->
                    <table cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td align="center" style="padding:8px 0 28px;">
                          <div style="display:inline-block;background:#fff7ed;border:2px solid #fdba74;
                                      border-radius:12px;padding:18px 40px;">
                            <span style="font-family:'JetBrains Mono',monospace;font-size:36px;
                                         font-weight:800;letter-spacing:0.18em;color:#c2410c;">
                              {otp_code}
                            </span>
                          </div>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:12.5px;color:#94a3b8;line-height:1.5;text-align:center;">
                      Nếu bạn không yêu cầu điều này, hãy bỏ qua email này.
                      Mật khẩu của bạn sẽ không thay đổi.
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="padding:16px 32px;border-top:1px solid #f1f5f9;
                             text-align:center;font-size:11px;color:#94a3b8;">
                    &copy; 2026 Neo-Kanban &mdash; AI-Agentic Project Management
                  </td>
                </tr>
              </table>
            </td></tr>
          </table>
        </body>
        </html>
    """)

    plain = dedent(f"""\
        Xin chào {display_name},

        Mã đặt lại mật khẩu Neo-Kanban của bạn là:

            {otp_code}

        Mã có hiệu lực trong 10 phút.

        Nếu bạn không yêu cầu điều này, hãy bỏ qua email này.

        — Neo-Kanban Team
    """)

    await _send(to_email, subject, html, plain)


async def send_welcome_email(to_email: str, display_name: str) -> None:
    """Send a welcome email after registration (optional — silently skipped if SMTP absent)."""
    subject = "Welcome to Neo-Kanban"

    html = dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"></head>
        <body style="margin:0;padding:40px 16px;background:#f8fafc;
                     font-family:'IBM Plex Sans',Arial,sans-serif;">
          <p style="font-size:18px;font-weight:600;color:#0f172a;">
            Hi {display_name}, welcome to NeoKanban!
          </p>
          <p style="font-size:14px;line-height:1.6;color:#475569;">
            Your account is ready. Start by creating a project and letting the AI
            Architect Agent generate your first SPEC and PLAN.
          </p>
        </body>
        </html>
    """)

    await _send(to_email, subject, html)
