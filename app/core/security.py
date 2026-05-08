from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── BCrypt Context (Industry Standard) ──────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    'sub' claim stores user email (as per specification).
    Expires based on ACCESS_TOKEN_EXPIRE_MINUTES from environment.
    Includes issued_at and jti claims for proper token tracking.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)  # From environment
    jti = f"access_{now.timestamp()}"
    
    payload = {
        "sub": subject,  # User email, not UUID
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "access",
        "iss": "weq-python-backend"
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """
    Long-lived refresh token based on REFRESH_TOKEN_EXPIRE_DAYS from environment.
    Claims 'type': 'refresh' to prevent misuse as access token.
    Includes jti for token rotation tracking.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)  # From environment
    jti = f"refresh_{now.timestamp()}"
    
    payload = {
        "sub": subject,  # User email
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
        "iss": "weq-python-backend"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodes and validates JWT. Raises JWTError on failure.
    Returns the full payload dict.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_token_subject(token: str) -> Optional[str]:
    """Safely extracts the 'sub' (user UUID) from a token without raising."""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None


def get_token_jti(token: str) -> Optional[str]:
    """Safely extracts 'jti' (JWT ID) from a token without raising."""
    try:
        payload = decode_token(token)
        return payload.get("jti")
    except JWTError:
        return None


def is_token_expired(token: str) -> bool:
    """Check if token is expired without raising exception."""
    try:
        payload = decode_token(token)
        exp = payload.get("exp")
        if not exp:
            return True
        return datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc)
    except JWTError:
        return True


def get_token_type(token: str) -> Optional[str]:
    """Safely extracts 'type' from a token without raising."""
    try:
        payload = decode_token(token)
        return payload.get("type")
    except JWTError:
        return None


def validate_access_token(token: str) -> dict:
    """
    Validates access token specifically.
    Returns payload if valid, raises HTTPException if invalid.
    """
    try:
        payload = decode_token(token)
        
        # Check token type
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        
        # Check issuer
        if payload.get("iss") != "weq-python-backend":
            raise JWTError("Invalid token issuer")
        
        return payload
    except JWTError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {str(e)}"
        )


def validate_refresh_token(token: str) -> dict:
    """
    Validates refresh token specifically.
    Returns payload if valid, raises HTTPException if invalid.
    """
    try:
        payload = decode_token(token)
        
        # Check token type
        if payload.get("type") != "refresh":
            raise JWTError("Invalid token type")
        
        # Check issuer
        if payload.get("iss") != "weq-python-backend":
            raise JWTError("Invalid token issuer")
        
        return payload
    except JWTError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}"
        )
