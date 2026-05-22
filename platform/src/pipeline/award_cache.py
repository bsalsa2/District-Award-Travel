import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aioredis
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Constants
AWARD_CACHE_TTL = 300  # 5 minutes
REDIS_URL = "redis://localhost:6379"
AIRLINE_CODES = ["AA", "DL", "UA", "BA", "JL", "QF", "EK", "LH"]
HOTEL_CHAINS = ["HILTON", "HYATT", "MARRIOTT", "IHG"]

class AwardCache:
    def __init__(self):
        self.redis = aioredis.from_url(REDIS_URL)
        self.local_cache = {}
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "set_operations": 0,
            "evictions": 0
        }

    async def _get_key(self, cache_type: str, key: str) -> Optional[Dict]:
        """Get value from cache with metrics tracking"""
        start_time = time.time()

        # Check local cache first
        if key in self.local_cache:
            self.metrics["hits"] += 1
            return self.local_cache[key]

        # Check Redis
        redis_key = f"{cache_type}:{key}"
        value = await self.redis.get(redis_key)

        if value:
            self.metrics["hits"] += 1
            self.local_cache[key] = json.loads(value)
            return self.local_cache[key]

        self.metrics["misses"] += 1
        return None

    async def _set_key(self, cache_type: str, key: str, value: Dict, ttl: int = AWARD_CACHE_TTL):
        """Set value in cache with metrics tracking"""
        self.metrics["set_operations"] += 1
        self.local_cache[key] = value

        redis_key = f"{cache_type}:{key}"
        await self.redis.setex(
            redis_key,
            ttl,
            json.dumps(value)
        )

    async def get_awards(self, origin: str, destination: str, date: str, cabin: str) -> List[Dict]:
        """Get award availability for flights"""
        cache_key = f"flight:{origin}:{destination}:{date}:{cabin}"
        cached = await self._get_key("flight", cache_key)

        if cached:
            return cached

        # Simulate award search (in production, this would call airline APIs)
        awards = self._simulate_award_search(origin, destination, date, cabin)
        await self._set_key("flight", cache_key, awards)
        return awards

    async def get_hotel_awards(self, property_id: str, check_in: str, check_out: str) -> List[Dict]:
        """Get award availability for hotels"""
        cache_key = f"hotel:{property_id}:{check_in}:{check_out}"
        cached = await self._get_key("hotel", cache_key)

        if cached:
            return cached

        # Simulate hotel award search
        awards = self._simulate_hotel_award_search(property_id, check_in, check_out)
        await self._set_key("hotel", cache_key, awards)
        return awards

    def _simulate_award_search(self, origin: str, destination: str, date: str, cabin: str) -> List[Dict]:
        """Simulate award search with realistic data"""
        # Generate realistic award availability
        airlines = [code for code in AIRLINE_CODES if np.random.random() > 0.3]
        flights = []

        for airline in airlines:
            for flight_num in range(100, 150):
                if np.random.random() > 0.7:  # 30% availability
                    flights.append({
                        "airline": airline,
                        "flight_number": f"{airline}{flight_num}",
                        "departure": origin,
                        "arrival": destination,
                        "departure_time": f"{np.random.randint(0, 23):02d}:{np.random.randint(0, 59):02d}",
                        "arrival_time": f"{np.random.randint(0, 23):02d}:{np.random.randint(0, 59):02d}",
                        "duration_minutes": np.random.randint(120, 600),
                        "award_miles": int(np.random.normal(30000, 5000)),
                        "cabin": cabin,
                        "seats_available": np.random.randint(1, 9),
                        "last_updated": datetime.utcnow().isoformat()
                    })

        return flights

    def _simulate_hotel_award_search(self, property_id: str, check_in: str, check_out: str) -> List[Dict]:
        """Simulate hotel award availability"""
        chains = [chain for chain in HOTEL_CHAINS if property_id.startswith(chain)]
        if not chains:
            return []

        hotels = []
        for chain in chains:
            for room_type in ["Standard", "Deluxe", "Suite"]:
                if np.random.random() > 0.4:  # 60% availability
                    hotels.append({
                        "property_id": f"{chain}-{property_id.split('-')[-1]}",
                        "property_name": f"{chain} {room_type} Room",
                        "check_in": check_in,
                        "check_out": check_out,
                        "nights": (datetime.strptime(check_out, "%Y-%m-%d") -
                                 datetime.strptime(check_in, "%Y-%m-%d")).days,
                        "award_points": int(np.random.normal(50000, 10000)),
                        "room_type": room_type,
                        "available_rooms": np.random.randint(1, 10),
                        "last_updated": datetime.utcnow().isoformat()
                    })

        return hotels

    async def invalidate_flights(self, origin: str, destination: str):
        """Invalidate flight cache for specific route"""
        pattern = f"flight:{origin}:{destination}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
            self.metrics["evictions"] += len(keys)

        # Clear local cache
        to_remove = [k for k in self.local_cache if k.startswith(f"flight:{origin}:{destination}")]
        for k in to_remove:
            del self.local_cache[k]

class AwardCacheMetrics(BaseModel):
    hits: int
    misses: int
    set_operations: int
    evictions: int
    cache_size: int
    redis_memory_usage: Optional[int] = None

# FastAPI app for cache management
app = FastAPI()
cache = AwardCache()

@app.get("/cache/metrics")
async def get_metrics() -> AwardCacheMetrics:
    """Get cache performance metrics"""
    return AwardCacheMetrics(
        hits=cache.metrics["hits"],
        misses=cache.metrics["misses"],
        set_operations=cache.metrics["set_operations"],
        evictions=cache.metrics["evictions"],
        cache_size=len(cache.local_cache)
    )

@app.post("/cache/invalidate/flights")
async def invalidate_flights(origin: str, destination: str):
    """Invalidate flight cache for specific route"""
    await cache.invalidate_flights(origin, destination)
    return {"status": "ok", "invalidated": f"{origin}-{destination}"}

@app.get("/awards/flights")
async def get_flight_awards(
    origin: str,
    destination: str,
    date: str,
    cabin: str = "economy"
):
    """Get flight award availability"""
    awards = await cache.get_awards(origin, destination, date, cabin)
    return {"awards": awards, "count": len(awards)}

@app.get("/awards/hotels")
async def get_hotel_awards(
    property_id: str,
    check_in: str,
    check_out: str
):
    """Get hotel award availability"""
    awards = await cache.get_hotel_awards(property_id, check_in, check_out)
    return {"awards": awards, "count": len(awards)}

async def startup_event():
    """Initialize cache on startup"""
    print("Award Cache Service initialized")

async def shutdown_event():
    """Cleanup on shutdown"""
    await cache.redis.close()

app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)
