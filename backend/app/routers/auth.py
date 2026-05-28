"""Auth endpoints: register, login, GitHub OAuth, forgot/reset password, current user."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerificationSentResponse,
    VerifyRegisterRequest,
    VerifyResetRequest,
)
from app.services import auth_service, email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# =========================================================================== #
# Register / Login / Me                                                        #
# =========================================================================== #

@router.post("/register", response_model=VerificationSentResponse, status_code=status.HTTP_200_OK)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> VerificationSentResponse:
    """Step 1 — validate registration data, send OTP to email.

    The user is NOT created yet. Call POST /auth/verify-register with the
    6-digit code to complete registration and receive a JWT.

    GitHub OAuth users skip this entirely (handled by /auth/github/callback).
    """
    import asyncio as _asyncio

    # Check email not taken
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password + generate OTP (store in Redis, NOT in DB yet)
    hashed_pw = await _asyncio.to_thread(auth_service.hash_password, body.password)
    otp_code = await auth_service.create_email_otp(
        email=body.email,
        hashed_password=hashed_pw,
        display_name=body.display_name,
    )

    # Dev fallback: always print OTP to console so developers can test without SMTP
    if not settings.smtp_host:
        logger.warning(
            "\n\n"
            "╔══════════════════════════════════════════════════╗\n"
            "║           DEV MODE — Email OTP (no SMTP)         ║\n"
            "╠══════════════════════════════════════════════════╣\n"
            "║  To : %-44s║\n"
            "║  Code: %-43s║\n"
            "╚══════════════════════════════════════════════════╝\n",
            body.email,
            otp_code,
        )

    # Fire-and-forget: send OTP email in background — never blocks or fails the response
    async def _send_otp_bg() -> None:
        try:
            await email_service.send_verification_otp_email(
                to_email=body.email,
                display_name=body.display_name,
                otp_code=otp_code,
            )
        except Exception:
            logger.exception("Failed to send OTP email to %s", body.email)

    import asyncio as _asyncio
    _asyncio.create_task(_send_otp_bg())

    return VerificationSentResponse(
        message="A 6-digit verification code has been sent to your email. Enter it to complete registration.",
        email=body.email,
    )


@router.post("/verify-register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def verify_register(
    body: VerifyRegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Step 2 — verify the OTP and create the user account.

    Returns a JWT token + user info on success.
    Raises 400 for wrong/expired code, 429 for too many attempts.
    """
    # Verify OTP + retrieve pending registration data
    pending = await auth_service.verify_email_otp(body.email, body.code)

    # Double-check email not stolen between steps
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user with pre-hashed password
    user = User(
        email=body.email,
        hashed_password=pending["hashed_password"],
        display_name=pending["display_name"],
    )
    session.add(user)
    await session.flush()

    token = auth_service.create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    await session.commit()
    await session.refresh(user)

    # Send welcome email (best-effort)
    try:
        await email_service.send_welcome_email(
            to_email=user.email,
            display_name=user.display_name,
        )
    except Exception:
        logger.debug("Welcome email failed (non-fatal)", exc_info=True)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password.

    - Validates credentials against PostgreSQL (bcrypt).
    - Returns a JWT valid for **7 days** plus the authenticated user object.
    - Updates ``last_login_at`` on the user row.
    - Raises 400 if the account was created via GitHub and has no password.
    - Raises 401 for wrong credentials.
    """
    user, token = await auth_service.login_user(
        session,
        body.email,
        body.password,
        settings,
    )
    await session.commit()
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# =========================================================================== #
# GitHub OAuth                                                                 #
# =========================================================================== #

@router.get("/github")
async def github_login_redirect() -> RedirectResponse:
    """Redirect the browser to GitHub's authorization page.

    The frontend can either:
      - Link directly to ``GET /api/v1/auth/github`` (full-page redirect), or
      - Build the GitHub URL client-side and pop up a window.

    Scope: ``user:email`` — minimum needed to read the primary email.
    """
    if not settings.github_oauth_client_id:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured on this server.",
        )

    import urllib.parse  # noqa: PLC0415

    params = urllib.parse.urlencode(
        {
            "client_id": settings.github_oauth_client_id,
            "redirect_uri": settings.github_oauth_redirect_uri,
            "scope": "user:email",
        }
    )
    return RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?{params}",
        status_code=302,
    )


@router.get(
    "/github/callback",
    summary="GitHub OAuth callback",
    response_class=RedirectResponse,
)
async def github_callback(
    code: Annotated[str, Query(description="Authorization code from GitHub.")],
    state: Annotated[str | None, Query()] = None,  # noqa: ARG001 — reserved for CSRF later
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the GitHub OAuth callback.

    Flow:
      1. Exchange *code* for a GitHub access token.
      2. Fetch ``/user`` (+ ``/user/emails``) from the GitHub API.
      3. Upsert the ``users`` row (create or link existing account by email).
      4. Issue a Neo-Kanban JWT.
      5. Redirect the browser to ``{FRONTEND_URL}/auth/callback?token={jwt}``.

    The frontend page at ``/auth/callback`` should read the ``token`` query
    param, store it in ``localStorage``, then navigate to ``/projects``.
    """
    gh_token = await auth_service.exchange_github_code(code, settings)
    user, jwt_token = await auth_service.get_or_create_github_user(
        session, gh_token, settings
    )
    await session.commit()
    await session.refresh(user)

    redirect_url = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=redirect_url, status_code=302)


# =========================================================================== #
# Forgot / Reset password                                                      #
# =========================================================================== #

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset OTP",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a 6-digit OTP to the given email for password reset.

    - Always returns **200** with the same message to prevent email enumeration.
    - The OTP is stored in Redis with a **10-minute TTL**.
    - In dev mode (SMTP not configured), the OTP is printed to the console.
    """
    user = await session.scalar(select(User).where(User.email == body.email))

    if user is not None:
        otp_code = await auth_service.create_password_reset_otp(user.email, user.id)
        logger.info("Password reset OTP requested for user_id=%s email=%s", user.id, body.email)

        # Dev fallback: print OTP to console when SMTP is not configured
        if not settings.smtp_host:
            logger.warning(
                "\n\n"
                "╔══════════════════════════════════════════════════╗\n"
                "║        DEV MODE — Password Reset OTP             ║\n"
                "╠══════════════════════════════════════════════════╣\n"
                "║  To : %-44s║\n"
                "║  Code: %-43s║\n"
                "╚══════════════════════════════════════════════════╝\n",
                body.email,
                otp_code,
            )

        # Fire-and-forget — never blocks the response
        _email = user.email
        _name = user.display_name
        _code = otp_code

        async def _send_reset_bg() -> None:
            try:
                await email_service.send_password_reset_otp_email(
                    to_email=_email,
                    display_name=_name,
                    otp_code=_code,
                )
            except Exception:
                logger.exception("Failed to deliver password-reset OTP email to %s", _email)

        import asyncio as _asyncio
        _asyncio.create_task(_send_reset_bg())

    return MessageResponse(
        message="Nếu email đó đã đăng ký, mã xác nhận đã được gửi. Kiểm tra hộp thư của bạn."
    )


@router.post(
    "/verify-reset",
    response_model=MessageResponse,
    summary="Verify OTP and set new password",
)
async def verify_reset(
    body: VerifyResetRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify the 6-digit OTP and update the user's password.

    - The OTP is consumed immediately (single-use).
    - All existing JWTs for this user are invalidated.
    - Returns 400 for wrong/expired code, 429 for too many attempts.
    """
    import asyncio as _asyncio

    user_id = await auth_service.verify_password_reset_otp(body.email, body.code)

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tài khoản không tồn tại.")

    user.hashed_password = await _asyncio.to_thread(auth_service.hash_password, body.new_password)
    await auth_service.revoke_all_user_tokens(user_id)
    await session.commit()

    return MessageResponse(message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using token from email (legacy link-based flow)",
)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Validate the reset token and update the user's password (legacy link flow).

    - The token is consumed immediately (single-use).
    - All existing JWTs for this user are **invalidated** via Redis.
    - Returns 400 for an invalid or expired token.
    """
    await auth_service.reset_user_password(session, body.token, body.new_password)
    await session.commit()

    return MessageResponse(
        message="Password reset successful. Please log in with your new password."
    )
