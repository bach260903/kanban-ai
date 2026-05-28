"""Auth endpoints: register, login, GitHub OAuth, forgot/reset password, current user."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
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
)
from app.services import auth_service, email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# =========================================================================== #
# Register / Login / Me                                                        #
# =========================================================================== #

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new account with email + password.  Returns JWT token + user info."""
    user = await auth_service.register_user(
        session,
        body.email,
        body.password,
        body.display_name,
    )
    token = auth_service.create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    await session.commit()
    await session.refresh(user)
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
    summary="Request a password reset email",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a password reset link to the given email address.

    - Always returns **200** with the same message to prevent email enumeration.
    - The reset token is stored in Redis with a **1-hour TTL**.
    - If SMTP is not configured, the token is generated but the email is only
      logged at WARNING level (useful for local development).
    """
    user = await session.scalar(select(User).where(User.email == body.email))

    if user is not None:
        reset_token = await auth_service.generate_password_reset_token(user.id)
        reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
        logger.info("Password reset requested for user_id=%s email=%s", user.id, body.email)

        try:
            await email_service.send_password_reset_email(
                to_email=user.email,
                display_name=user.display_name,
                reset_link=reset_link,
            )
        except Exception:
            # Never let SMTP failure block the 200 response
            logger.exception("Failed to deliver password-reset email to %s", body.email)

    return MessageResponse(
        message="If that email is registered, a reset link has been sent. Check your inbox."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using token from email",
)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Validate the reset token and update the user's password.

    - The token is consumed immediately (single-use).
    - All existing JWTs for this user are **invalidated** via Redis so old
      sessions (e.g. stolen tokens) cannot be used after the reset.
    - Returns 400 for an invalid or expired token.
    """
    await auth_service.reset_user_password(session, body.token, body.new_password)
    await session.commit()

    return MessageResponse(
        message="Password reset successful. Please log in with your new password."
    )
