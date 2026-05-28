"""Authentication helpers: password hashing, JWT, register/login/OAuth/reset."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import bcrypt
import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User

# Redis TTLs
_RESET_TOKEN_TTL_SEC: int = 3600           # 1 hour  — password reset token
_REVOKE_KEY_TTL_SEC: int = 8 * 24 * 3600  # 8 days  — slightly > JWT 7-day expiry
_OTP_TTL_SEC: int = 600                   # 10 min  — email verification OTP
_OTP_MAX_ATTEMPTS: int = 5               # max wrong guesses before lockout


class _TokenData(NamedTuple):
    user_id: uuid.UUID
    iat: int  # issued-at (UNIX timestamp)


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (compatible with existing ``security.py`` hashes)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: uuid.UUID,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> str:
    """Create a signed JWT for the given user id."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=expire_days)
    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str) -> uuid.UUID:
    """Decode and validate a JWT; return the user id from ``sub``."""
    return decode_token_full(token, secret, algorithm).user_id


def decode_token_full(token: str, secret: str, algorithm: str) -> _TokenData:
    """Decode and validate a JWT; return ``(user_id, iat)`` for revocation checks."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
        iat = int(payload.get("iat", 0))
        return _TokenData(user_id=uuid.UUID(str(sub)), iat=iat)
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


# =========================================================================== #
# Email OTP verification (registration)                                        #
# =========================================================================== #

async def create_email_otp(
    email: str,
    hashed_password: str,
    display_name: str,
) -> str:
    """Generate a 6-digit OTP, persist it (with pending registration data) in Redis.

    Returns the OTP code (caller sends it by email).
    The key expires after 10 minutes.
    """
    import json as _json

    code = f"{secrets.randbelow(1_000_000):06d}"
    r = await _get_redis()
    key = f"email_otp:{email.lower()}"
    payload = _json.dumps({
        "code": code,
        "hashed_password": hashed_password,
        "display_name": display_name,
    })
    await r.setex(key, _OTP_TTL_SEC, payload)
    # reset attempt counter
    await r.delete(f"email_otp_attempts:{email.lower()}")
    return code


async def verify_email_otp(email: str, code: str) -> dict:
    """Verify the OTP submitted by the user.

    Returns the pending registration dict ``{hashed_password, display_name}``
    on success. Raises 400/429 on failure.
    """
    import json as _json

    r = await _get_redis()
    email_lower = email.lower()
    key = f"email_otp:{email_lower}"
    attempts_key = f"email_otp_attempts:{email_lower}"

    raw: str | None = await r.get(key)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired or not found. Please register again.",
        )

    attempts = int(await r.get(attempts_key) or 0)
    if attempts >= _OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please register again with a new code.",
        )

    data = _json.loads(raw)
    if data["code"] != code.strip():
        await r.incr(attempts_key)
        await r.expire(attempts_key, _OTP_TTL_SEC)
        remaining = _OTP_MAX_ATTEMPTS - attempts - 1
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect verification code. {remaining} attempt(s) remaining.",
        )

    # Correct — consume OTP
    await r.delete(key)
    await r.delete(attempts_key)
    return {"hashed_password": data["hashed_password"], "display_name": data["display_name"]}


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Register a new user; raise 409 if email already exists."""
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=email,
        hashed_password=await asyncio.to_thread(hash_password, password),
        display_name=display_name,
    )
    session.add(user)
    await session.flush()
    return user


async def login_user(
    session: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
) -> tuple[User, str]:
    """Authenticate user and return (user, access_token).

    Raises 401 for wrong credentials.  Raises 400 if the account was created
    via GitHub OAuth and has no password set yet.
    """
    user = await session.scalar(select(User).where(User.email == email))

    # GitHub-only account — no password
    if user is not None and user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses GitHub login. Please sign in with GitHub.",
        )

    password_ok = user is not None and await asyncio.to_thread(
        verify_password,
        password,
        user.hashed_password,  # type: ignore[arg-type]  — checked above
    )
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    user.last_login_at = datetime.now(timezone.utc)
    token = create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    return user, token


# =========================================================================== #
# Redis helpers (lazy import to avoid circular deps at module load time)       #
# =========================================================================== #

async def _get_redis():  # type: ignore[return]
    """Lazily import and return the shared async Redis client."""
    from app.websocket.event_publisher import _get_redis as _pub_redis  # noqa: PLC0415
    return await _pub_redis()


# =========================================================================== #
# Token revocation                                                             #
# =========================================================================== #

async def revoke_all_user_tokens(user_id: uuid.UUID) -> None:
    """Record current timestamp in Redis so all JWTs issued before now are rejected.

    TTL is set to 8 days (slightly > JWT 7-day expiry) so the key auto-expires
    after all affected tokens have naturally expired.
    """
    r = await _get_redis()
    key = f"user_tokens_revoked_before:{user_id}"
    now_ts = int(datetime.now(timezone.utc).timestamp())
    await r.setex(key, _REVOKE_KEY_TTL_SEC, str(now_ts))


async def is_token_revoked(user_id: uuid.UUID, iat: int) -> bool:
    """Return True if the JWT was issued at or before the revocation timestamp."""
    r = await _get_redis()
    val: str | None = await r.get(f"user_tokens_revoked_before:{user_id}")
    if not val:
        return False
    return iat <= int(val)


# =========================================================================== #
# Password reset                                                               #
# =========================================================================== #

async def generate_password_reset_token(user_id: uuid.UUID) -> str:
    """Create a 32-byte URL-safe token, store in Redis for 1 hour, return it."""
    token = secrets.token_urlsafe(32)
    r = await _get_redis()
    await r.setex(f"pwd_reset:{token}", _RESET_TOKEN_TTL_SEC, str(user_id))
    return token


async def create_password_reset_otp(email: str, user_id: uuid.UUID) -> str:
    """Generate a 6-digit OTP for password reset; store user_id in Redis.

    Key: ``pwd_reset_otp:{email.lower()}``  TTL: 10 minutes.
    Attempt counter: ``pwd_reset_otp_attempts:{email.lower()}``
    Returns the OTP code (caller sends it by email).
    """
    import json as _json

    code = f"{secrets.randbelow(1_000_000):06d}"
    r = await _get_redis()
    key = f"pwd_reset_otp:{email.lower()}"
    payload = _json.dumps({"code": code, "user_id": str(user_id)})
    await r.setex(key, _OTP_TTL_SEC, payload)
    await r.delete(f"pwd_reset_otp_attempts:{email.lower()}")
    return code


async def verify_password_reset_otp(email: str, code: str) -> uuid.UUID:
    """Verify the OTP for password reset; return user_id on success.

    Raises 400 for wrong/expired code, 429 for too many attempts.
    Consumes the OTP on success (single-use).
    """
    import json as _json

    r = await _get_redis()
    email_lower = email.lower()
    key = f"pwd_reset_otp:{email_lower}"
    attempts_key = f"pwd_reset_otp_attempts:{email_lower}"

    raw: str | None = await r.get(key)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã xác nhận đã hết hạn hoặc không tồn tại. Vui lòng yêu cầu mã mới.",
        )

    attempts = int(await r.get(attempts_key) or 0)
    if attempts >= _OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều lần thử sai. Vui lòng yêu cầu mã mới.",
        )

    data = _json.loads(raw)
    if data["code"] != code.strip():
        await r.incr(attempts_key)
        await r.expire(attempts_key, _OTP_TTL_SEC)
        remaining = _OTP_MAX_ATTEMPTS - attempts - 1
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã xác nhận không đúng. Còn {remaining} lần thử.",
        )

    # Correct — consume OTP
    await r.delete(key)
    await r.delete(attempts_key)
    return uuid.UUID(data["user_id"])


async def get_user_id_from_reset_token(token: str) -> uuid.UUID | None:
    """Return the user_id associated with *token*, or None if not found / expired."""
    r = await _get_redis()
    val: str | None = await r.get(f"pwd_reset:{token}")
    if not val:
        return None
    try:
        return uuid.UUID(val)
    except ValueError:
        return None


async def consume_reset_token(token: str) -> None:
    """Delete the reset token from Redis so it cannot be reused."""
    r = await _get_redis()
    await r.delete(f"pwd_reset:{token}")


async def reset_user_password(
    session: AsyncSession,
    reset_token: str,
    new_password: str,
) -> User:
    """Validate *reset_token*, update the user's password, invalidate all old JWTs.

    Raises 400 for invalid/expired token.
    """
    user_id = await get_user_id_from_reset_token(reset_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    user.hashed_password = await asyncio.to_thread(hash_password, new_password)

    # Single-use: delete the token immediately
    await consume_reset_token(reset_token)

    # Invalidate all JWTs issued before now (old sessions / stolen tokens)
    await revoke_all_user_tokens(user_id)

    return user


# =========================================================================== #
# GitHub OAuth                                                                 #
# =========================================================================== #

async def exchange_github_code(code: str, settings: Settings) -> str:
    """Exchange an OAuth *code* for a GitHub access token.

    Returns the ``access_token`` string or raises 400/502 on failure.
    """
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured on this server.",
        )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned an unexpected response during token exchange.",
        )

    data: dict = resp.json()
    if "error" in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth error: {data.get('error_description') or data['error']}",
        )

    return str(data["access_token"])


async def _fetch_github_primary_email(
    client: httpx.AsyncClient,
    gh_token: str,
) -> str | None:
    """Fetch the primary verified email from GET /user/emails."""
    try:
        resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        for entry in resp.json():
            if isinstance(entry, dict) and entry.get("primary") and entry.get("verified"):
                return str(entry["email"])
    except Exception:  # pragma: no cover
        pass
    return None


async def get_or_create_github_user(
    session: AsyncSession,
    gh_access_token: str,
    settings: Settings,
) -> tuple[User, str]:
    """Fetch GitHub profile, upsert User row, return *(user, jwt)*.

    Strategy (in order):
      1. Find existing user by github_id  → link / update profile.
      2. Find existing user by verified email  → link GitHub to that account.
      3. Create a brand-new user.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {gh_access_token}",
                "Accept": "application/json",
            },
        )

        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch GitHub user profile.",
            )

        gh_profile: dict = user_resp.json()

        # GitHub may omit public email — fall back to /user/emails
        email: str | None = gh_profile.get("email") or None
        if not email:
            email = await _fetch_github_primary_email(client, gh_access_token)

    github_id = str(gh_profile["id"])
    display_name: str = gh_profile.get("name") or gh_profile.get("login") or "GitHub User"
    avatar_url: str | None = gh_profile.get("avatar_url") or None

    # 1. Look up by github_id
    user: User | None = await session.scalar(
        select(User).where(User.github_id == github_id)
    )

    # 2. Look up by email (account linking)
    if user is None and email:
        user = await session.scalar(select(User).where(User.email == email))

    # 3. Create new user
    if user is None:
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Your GitHub account has no verified email address. "
                    "Please add a verified email to your GitHub account and try again."
                ),
            )
        user = User(
            email=email,
            hashed_password=None,
            display_name=display_name,
            github_id=github_id,
            avatar_url=avatar_url,
        )
        session.add(user)
        await session.flush()
    else:
        # Update GitHub identity on existing account
        user.github_id = github_id
        if avatar_url:
            user.avatar_url = avatar_url
        # Only overwrite display_name if the user hasn't customised it
        if not user.display_name or user.display_name == "GitHub User":
            user.display_name = display_name

    user.last_login_at = datetime.now(timezone.utc)

    jwt_token = create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    return user, jwt_token
