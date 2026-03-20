from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Argon2 Context ────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Mirrors Java BCryptPasswordEncoder logic but with modern Argon2."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Mirrors Java BCryptPasswordEncoder.matches()."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Helpers ───────────────────────────────────────────────────────────────
def create_access_token(subject: str, extra_claims: Optional[dict] = None) -> str:
    """
    Mirrors Java JwtUtils.generateToken().
    'sub' claim stores user email (as per blueprint spec).
    Expires in ACCESS_TOKEN_EXPIRE_MINUTES (default 15 min).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Long-lived refresh token (7 days by default).
    Claims 'type': 'refresh' to prevent misuse as access token.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodes and validates JWT. Raises JWTError on failure.
    Returns the full payload dict.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_token_subject(token: str) -> Optional[str]:
    """Safely extracts the 'sub' (email) from a token without raising."""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None
