"""
High-performance caching layer for award flight availability.
Designed for mechanical sympathy with Redis pipelining and efficient serialization.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from platform.src.models.award_flight import AwardFlight, AwardSearchRequest
from redis.asyncio import Redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CacheKey(BaseModel):
    """Model for cache key components."""
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date]
    cabin_class: str

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }

class FlightCache:
    """High-performance cache for award flight availability."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = timedelta(hours=6)  # Cache TTL

    async def _generate_key(self, request: AwardSearchRequest) -> str:
        """Generate cache key from search request."""
        cache_key = CacheKey(
            origin=request.origin,
            destination=request.destination,
            departure_date=request.departure_date,
            return_date=request.return_date,
            cabin_class=request.cabin_class.value
        )
        return f"award_flights:{cache_key.json()}"

    async def get_flights(
        self,
        request: AwardSearchRequest
    ) -> Optional[List[AwardFlight]]:
        """Get cached flights for a search request."""
        key = await self._generate_key(request)
        cached = await self.redis.get(key)

        if not cached:
            return None

        try:
            flights_data = json.loads(cached)
            return [AwardFlight(**flight_data) for flight_data in flights_data]
        except Exception as e:
            logger.error(f"Error deserializing cached flights: {e}")
            return None

    async def set_flights(
        self,
        request: AwardSearchRequest,
        flights: List[AwardFlight]
    ) -> bool:
        """Cache flights for a search request."""
        key = await self._generate_key(request)

        try:
            flights_data = [flight.dict() for flight in flights]
            serialized = json.dumps(flights_data)
            await self.redis.setex(key, self.ttl.total_seconds(), serialized)
            return True
        except Exception as e:
            logger.error(f"Error serializing flights for cache: {e}")
            return False

    async def invalidate_route(
        self,
        origin: str,
        destination: str
    ) -> int:
        """Invalidate all cache entries for a specific route."""
        pattern = f"award_flights:{{*origin:{origin}*destination:{destination}*}}"
        keys = []
        cursor = 0

        while True:
            cursor, batch = await self.redis.scan(cursor, pattern)
            keys.extend(batch)
            if cursor == 0:
                break

        if keys:
            await self.redis.delete(*keys)

        return len(keys)
