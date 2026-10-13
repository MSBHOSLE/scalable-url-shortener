"""Redis Cache Service for Read-Through Caching and Counter Management."""

import json
from typing import Any, Optional
import redis.asyncio as redis
from app.core.config import settings
from app.core.logging import logger


class CacheService:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.client: Optional[redis.Redis] = None
        self._enabled = settings.ENABLE_CACHE and bool(self.redis_url)

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if not self._enabled:
            return
        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            await self.client.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis cache: {e}. Running in cache-fallback mode.")
            self.client = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def get(self, key: str) -> Optional[str]:
        """Fetch value from cache."""
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self.client:
            return False
        try:
            ttl_seconds = ttl or settings.CACHE_TTL_SECONDS
            await self.client.set(key, value, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.warning(f"Redis SET failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Evict key from cache."""
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE failed for key {key}: {e}")
            return False

    async def incr(self, key: str) -> Optional[int]:
        """Increment integer key in Redis (e.g. click count or rate limiting)."""
        if not self.client:
            return None
        try:
            return await self.client.incr(key)
        except Exception as e:
            logger.warning(f"Redis INCR failed for key {key}: {e}")
            return None

    # URL-specific helper methods
    def _url_key(self, short_code: str) -> str:
        return f"url:{short_code}"

    async def get_url(self, short_code: str) -> Optional[dict]:
        raw = await self.get(self._url_key(short_code))
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    async def set_url(self, short_code: str, data: dict, ttl: Optional[int] = None) -> bool:
        return await self.set(self._url_key(short_code), json.dumps(data), ttl=ttl)

    async def invalidate_url(self, short_code: str) -> bool:
        return await self.delete(self._url_key(short_code))


cache_service = CacheService()
