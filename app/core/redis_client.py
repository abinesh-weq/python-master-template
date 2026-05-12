import json
import redis.asyncio as redis
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.core.config import settings


class RedisClient:
    """Async Redis client wrapper with error handling."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Initialize Redis connection."""
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def set_hash(self, key: str, data: Dict[str, Any], ttl_seconds: int = None) -> bool:
        """Set hash with optional TTL."""
        if not self._connected or not self.redis:
            return False
        
        try:
            await self.redis.hset(key, mapping=data)
            if ttl_seconds:
                await self.redis.expire(key, ttl_seconds)
            return True
        except Exception:
            return False
    
    async def get_hash(self, key: str) -> Optional[Dict[str, str]]:
        """Get hash data."""
        if not self._connected or not self.redis:
            return None
        
        try:
            data = await self.redis.hgetall(key)
            return data if data else None
        except Exception:
            return None
    
    async def delete_key(self, key: str) -> bool:
        """Delete key."""
        if not self._connected or not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception:
            return False
    
    async def increment_field(self, key: str, field: str) -> Optional[int]:
        """Increment hash field value."""
        if not self._connected or not self.redis:
            return None
        
        try:
            return await self.redis.hincrby(key, field, 1)
        except Exception:
            return None


# Global Redis client instance
redis_client = RedisClient()
