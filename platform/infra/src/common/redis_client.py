import redis.asyncio as redis
from config import config
from typing import Optional, Any, List, Dict
from common.logger import logger
import json
from datetime import timedelta

class RedisClient:
    def __init__(self):
        self.client = None
        self.config = config.redis

    async def initialize(self):
        """Initialize the Redis client."""
        try:
            self.client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Redis client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise

    async def close(self):
        """Close the Redis client."""
        if self.client:
            await self.client.close()
            logger.info("Redis client closed")

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if ttl:
                await self.client.setex(key, timedelta(seconds=ttl), value)
            else:
                await self.client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis."""
        try:
            value = await self.client.get(key)
            if value is None:
                return None

            # Try to parse as JSON if it starts with { or [
            if value.startswith('{') or value.startswith('['):
                return json.loads(value)
            return value
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            result = await self.client.delete(key)
            return result == 1
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        try:
            return await self.client.exists(key) == 1
        except Exception as e:
            logger.error(f"Failed to check key {key}: {e}")
            return False

    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set a hash field in Redis."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return await self.client.hset(key, field, value) == 1
        except Exception as e:
            logger.error(f"Failed to set hash field {field} in key {key}: {e}")
            return False

    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get a hash field from Redis."""
        try:
            value = await self.client.hget(key, field)
            if value is None:
                return None

            if value.startswith('{') or value.startswith('['):
                return json.loads(value)
            return value
        except Exception as e:
            logger.error(f"Failed to get hash field {field} from key {key}: {e}")
            return None

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields from Redis."""
        try:
            result = await self.client.hgetall(key)
            return {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v
                   for k, v in result.items()}
        except Exception as e:
            logger.error(f"Failed to get all hash fields from key {key}: {e}")
            return {}

    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to a Redis list."""
        try:
            if values:
                # Convert all values to strings
                str_values = [json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                            for v in values]
                return await self.client.lpush(key, *str_values)
            return 0
        except Exception as e:
            logger.error(f"Failed to push to list {key}: {e}")
            return 0

    async def rpop(self, key: str) -> Optional[Any]:
        """Pop a value from a Redis list."""
        try:
            value = await self.client.rpop(key)
            if value is None:
                return None

            if value.startswith('{') or value.startswith('['):
                return json.loads(value)
            return value
        except Exception as e:
            logger.error(f"Failed to pop from list {key}: {e}")
            return None

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a Redis channel."""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            return await self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")
            return 0

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel."""
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to channel {channel}: {e}")
            raise

# Global Redis instance
redis_client = RedisClient()
