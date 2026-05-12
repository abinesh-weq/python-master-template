import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.otp.models import OTPVerification
from app.core.security import pwd_context
from app.core.config import settings
from app.core.redis_client import redis_client

class OTPService:
    @staticmethod
    def generate_code() -> str:
        """Generate a secure 6-digit OTP."""
        return str(secrets.randbelow(900_000) + 100_000)
    
    def _get_redis_key(self, identifier: str, otp_type: str) -> str:
        """Generate Redis key for OTP."""
        return f"otp:{identifier.lower()}:{otp_type.upper()}"
    
    async def _send_otp_redis(self, identifier: str, otp_type: str, expire_minutes: int = 5) -> str:
        """Send OTP using Redis storage."""
        if not redis_client.is_connected:
            raise Exception("Redis not available")
        
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        redis_key = self._get_redis_key(identifier, otp_type)
        
        # Generate new OTP
        otp_code = self.generate_code()
        otp_hash = pwd_context.hash(otp_code)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Store in Redis as hash
        otp_data = {
            "identifier": identifier,
            "otp_type": otp_type,
            "otp_hash": otp_hash,
            "created_at": now.isoformat(),
            "attempt_count": "0"
        }
        
        success = await redis_client.set_hash(
            redis_key, 
            otp_data, 
            ttl_seconds=expire_minutes * 60
        )
        
        if not success:
            raise Exception("Failed to store OTP in Redis")
        
        return otp_code
    
    async def _get_verification_redis(self, identifier: str, otp_type: str) -> Optional[Dict[str, str]]:
        """Get OTP verification from Redis."""
        if not redis_client.is_connected:
            return None
        
        redis_key = self._get_redis_key(identifier.lower(), otp_type.upper())
        return await redis_client.get_hash(redis_key)
    
    async def _verify_otp_redis(self, identifier: str, otp_type: str, otp_code: str) -> bool:
        """Verify OTP using Redis storage."""
        if not redis_client.is_connected:
            return False
        
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        redis_key = self._get_redis_key(identifier, otp_type)
        
        otp_data = await redis_client.get_hash(redis_key)
        if not otp_data:
            return False
        
        # Check attempt limits
        attempt_count = int(otp_data.get("attempt_count", "0"))
        if attempt_count >= 5:
            await redis_client.delete_key(redis_key)
            return False
        
        # Verify hash
        is_valid = pwd_context.verify(otp_code, otp_data["otp_hash"])
        
        if is_valid:
            # Consume OTP
            await redis_client.delete_key(redis_key)
            return True
        else:
            # Increment attempt count
            await redis_client.increment_field(redis_key, "attempt_count")
        
        return is_valid
    
    async def _invalidate_otp_redis(self, identifier: str, otp_type: str):
        """Invalidate OTP in Redis."""
        if not redis_client.is_connected:
            return
        
        redis_key = self._get_redis_key(identifier.lower(), otp_type.upper())
        await redis_client.delete_key(redis_key)

    async def get_verification(self, db: AsyncSession, identifier: str, otp_type: str) -> Optional[OTPVerification]:
        result = await db.execute(
            select(OTPVerification).where(
                OTPVerification.identifier == identifier.lower(),
                OTPVerification.otp_type == otp_type.upper()
            )
        )
        return result.scalar_one_or_none()

    async def send_otp(self, db: AsyncSession, identifier: str, otp_type: str, expire_minutes: int = 5) -> str:
        """
        Market Standard: Upsert OTP.
        If existing valid OTP exists, it will be replaced by a new one for security.
        Uses Redis if configured, otherwise falls back to database.
        """
        # Use Redis if configured and available
        if settings.OTP_STORAGE_TYPE.upper() == "REDIS":
            try:
                return await self._send_otp_redis(identifier, otp_type, expire_minutes)
            except Exception:
                # Fallback to database if Redis fails
                pass
        
        # Database storage (original logic)
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # 1. Check existing
        existing = await self.get_verification(db, identifier, otp_type)
        
        # 2. Generate New
        otp_code = self.generate_code()
        otp_hash = pwd_context.hash(otp_code)
        expires_at = now + timedelta(minutes=expire_minutes)

        if existing:
            existing.otp_hash = otp_hash
            existing.expires_at = expires_at
            existing.attempt_count = 0
            existing.verified_at = None
        else:
            new_otp = OTPVerification(
                identifier=identifier,
                otp_type=otp_type,
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempt_count=0
            )
            db.add(new_otp)
        
        await db.commit()
        return otp_code

    async def verify_otp(self, db: AsyncSession, identifier: str, otp_type: str, otp_code: str) -> bool:
        """
        Verifies OTP against hash. 
        Checks expiry and attempt limits.
        Uses Redis if configured, otherwise falls back to database.
        """
        # Use Redis if configured and available
        if settings.OTP_STORAGE_TYPE.upper() == "REDIS":
            try:
                return await self._verify_otp_redis(identifier, otp_type, otp_code)
            except Exception:
                # Fallback to database if Redis fails
                pass
        
        # Database verification (original logic)
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        otp_record = await self.get_verification(db, identifier, otp_type)
        if not otp_record:
            return False
            
        # 1. Check Expiry
        if now > otp_record.expires_at:
            return False
            
        # 2. Check Attempt Limits (Max 5)
        if otp_record.attempt_count >= 5:
            return False
            
        # 3. Verify Hash
        is_valid = pwd_context.verify(otp_code, otp_record.otp_hash)
        
        if is_valid:
            # Consume OTP after successful verification
            await self.invalidate_otp(db, identifier, otp_type)
            return True
        else:
            otp_record.attempt_count += 1
            
        await db.commit()
        return is_valid

    async def invalidate_otp(self, db: AsyncSession, identifier: str, otp_type: str):
        """Consume OTP after final use (registration)."""
        # Use Redis if configured and available
        if settings.OTP_STORAGE_TYPE.upper() == "REDIS":
            try:
                await self._invalidate_otp_redis(identifier, otp_type)
                return
            except Exception:
                # Fallback to database if Redis fails
                pass
        
        # Database invalidation (original logic)
        await db.execute(
            delete(OTPVerification).where(
                OTPVerification.identifier == identifier.lower(),
                OTPVerification.otp_type == otp_type.upper()
            )
        )
        await db.commit()

otp_service = OTPService()
