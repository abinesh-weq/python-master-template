import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple


class OTPCache:
    """
    In-memory OTP store with per-entry TTL.
    Mirrors Java Caffeine cache used for OTP verification.

    Storage shape: { cache_key: (otp_value, expiry_datetime) }
    """

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, datetime]] = {}
        self._lock = asyncio.Lock()

    # ── Internal ──────────────────────────────────────────────────────────────
    def _key(self, identifier: str, otp_type: str) -> str:
        return f"{otp_type.upper()}:{identifier.lower()}"

    # ── Public API ────────────────────────────────────────────────────────────
    @staticmethod
    def generate() -> str:
        """Generate a secure 6-digit OTP."""
        return str(secrets.randbelow(900_000) + 100_000)

    async def store(
        self, identifier: str, otp_type: str, otp: str, expire_minutes: int = 5
    ) -> None:
        """Store OTP with expiry. Overwrites any existing OTP for same key."""
        async with self._lock:
            expiry = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
            self._store[self._key(identifier, otp_type)] = (otp, expiry)

    async def verify(self, identifier: str, otp_type: str, otp: str) -> bool:
        """
        Verifies OTP. Deletes entry on success OR expiry (one-time use).
        Returns True only if OTP matches and has not expired.
        """
        async with self._lock:
            key = self._key(identifier, otp_type)
            entry = self._store.get(key)
            if not entry:
                return False
            stored_otp, expiry = entry
            if datetime.now(timezone.utc) > expiry:
                del self._store[key]
                return False
            if stored_otp != otp:
                return False
            del self._store[key]  # Consume — no replay attacks
            return True

    async def peek(self, identifier: str, otp_type: str) -> Optional[str]:
        """Returns OTP value without consuming it (used for testing/debug)."""
        async with self._lock:
            key = self._key(identifier, otp_type)
            entry = self._store.get(key)
            if not entry:
                return None
            stored_otp, expiry = entry
            if datetime.now(timezone.utc) > expiry:
                del self._store[key]
                return None
            return stored_otp

    async def purge_expired(self) -> None:
        """Background cleanup — call periodically if needed."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]


# ── Singleton ─────────────────────────────────────────────────────────────────
otp_cache = OTPCache()
