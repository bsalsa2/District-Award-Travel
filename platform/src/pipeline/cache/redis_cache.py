"""
Redis Cache Layer for External API Responses
Implements distributed caching with TTL and automatic cleanup
"""

import redis.asyncio as redis
import logging
from typing import Optional, Any
import json
from platform.src.pipeline.external_api.exceptions import CacheError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class RedisCache:
    """Wrapper around Redis for caching API responses"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self._redis = None

    async def __aenter__(self):
        self._redis = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._redis:
            await self._redis.close()

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a key-value pair with TTL in seconds"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            result = await self._redis.setex(key, ttl, value)
            return result == "OK"
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {str(e)}")
            raise CacheError(f"Cache set failed: {str(e)}")

    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            value = await self._redis.get(key)
            return value
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {str(e)}")
            raise CacheError(f"Cache get failed: {str(e)}")

    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            result = await self._redis.delete(key)
            return result == 1
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {str(e)}")
            raise CacheError(f"Cache delete failed: {str(e)}")

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            return await self._redis.exists(key) == 1
        except Exception as e:
            logger.error(f"Failed to check cache key {key}: {str(e)}")
            raise CacheError(f"Cache exists check failed: {str(e)}")

    async def clear_all(self) -> int:
        """Clear all keys in the current database (use with caution)"""
        try:
            return await self._redis.flushdb()
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")
            raise CacheError(f"Cache clear failed: {str(e)}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = await self._redis.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "keys": info.get("db0", {}).get("keys", 0),
                "uptime": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {
                "error": str(e),
                "connected_clients": 0,
                "used_memory": 0,
                "keys": 0,
                "uptime": 0
            }
