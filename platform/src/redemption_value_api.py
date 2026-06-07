"""
Client Redemption Value Analytics API
High-performance endpoint for calculating redemption values from award flight bookings.
Designed for low-latency, high-throughput operations with mechanical sympathy.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# Configure logging with mechanical sympathy - avoid blocking I/O
LOG_DIR = Path("/var/log/district_award_travel")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "redemption_value_api.log"

# Rotating file handler to prevent log file from growing too large
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Console handler for development
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger("redemption_value_api")
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

# Performance monitoring
class PerformanceMonitor:
    """Thread-safe performance monitoring with mechanical sympathy"""

    def __init__(self):
        self.metrics = {
            'request_count': 0,
            'total_latency': 0.0,
            'max_latency': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'db_queries': 0,
            'last_reset': datetime.utcnow()
        }
        self.lock = asyncio.Lock()

    async def record_request(self, latency: float, cache_hit: bool = False):
        async with self.lock:
            self.metrics['request_count'] += 1
            self.metrics['total_latency'] += latency
            self.metrics['max_latency'] = max(self.metrics['max_latency'], latency)
            if cache_hit:
                self.metrics['cache_hits'] += 1
            else:
                self.metrics['cache_misses'] += 1

    async def record_db_query(self):
        async with self.lock:
            self.metrics['db_queries'] += 1

    async def get_metrics(self) -> Dict[str, Any]:
        async with self.lock:
            return self.metrics.copy()

    async def reset_metrics(self):
        async with self.lock:
            self.metrics['request_count'] = 0
            self.metrics['total_latency'] = 0.0
            self.metrics['max_latency'] = 0.0
            self.metrics['cache_hits'] = 0
            self.metrics['cache_misses'] = 0
            self.metrics['db_queries'] = 0
            self.metrics['last_reset'] = datetime.utcnow()

performance_monitor = PerformanceMonitor()

# Redis cache configuration with connection pooling
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Cache TTLs - designed for mechanical sympathy
CACHE_TTL_SHORT = 300  # 5 minutes for frequently accessed data
CACHE_TTL_MEDIUM = 3600  # 1 hour for less frequently accessed
CACHE_TTL_LONG = 86400  # 24 hours for rarely changing data

class RedemptionValueRequest(BaseModel):
    """Request model for redemption value calculation"""
    client_id: str = Field(..., description="Unique client identifier")
    redemption_id: Optional[str] = Field(None, description="Specific redemption ID to calculate")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format")
    cabin_class: Optional[str] = Field(None, description="Filter by cabin class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)")
    airline_codes: Optional[List[str]] = Field(None, description="Filter by airline codes")
    limit: Optional[int] = Field(100, description="Maximum number of results to return", ge=1, le=1000)

class RedemptionValueResponse(BaseModel):
    """Response model for redemption value calculation"""
    client_id: str
    redemption_id: str
    booking_reference: str
    flight_details: Dict[str, Any]
    redemption_value: float
    currency: str
    redemption_date: str
    cabin_class: str
    airline: str
    distance: int
    fare_basis: str
    status: str
    calculated_at: str
    metadata: Dict[str, Any]

class RedemptionValueSummary(BaseModel):
    """Summary response for multiple redemptions"""
    client_id: str
    total_redemptions: int
    total_value: float
    average_value: float
    min_value: float
    max_value: float
    currency: str
    redemptions: List[RedemptionValueResponse]
    calculated_at: str
    period_start: Optional[str]
    period_end: Optional[str]

class RedemptionValueCalculator:
    """
    High-performance redemption value calculator with mechanical sympathy.
    Designed for low-latency, high-throughput operations.
    """

    def __init__(self):
        self.redis = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection with connection pooling"""
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                max_connections=50  # Connection pool size
            )
            # Test connection
            if self.redis.ping():
                logger.info("Redis connection established successfully")
            else:
                logger.warning("Redis connection test failed, will retry on first use")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.redis = None

    async def _get_cache(self, key: str) -> Optional[Dict]:
        """Get cached value with mechanical sympathy - non-blocking"""
        if not self.redis:
            return None

        try:
            cached = await self.redis.get(key)
            if cached:
                await performance_monitor.record_request(0.001, cache_hit=True)  # Tiny latency for cache hit
                return json.loads(cached)
            await performance_monitor.record_request(0.001, cache_hit=False)
            return None
        except Exception as e:
            logger.error(f"Redis cache error: {e}")
            return None

    async def _set_cache(self, key: str, value: Dict, ttl: int):
        """Set cached value with mechanical sympathy - non-blocking"""
        if not self.redis:
            return

        try:
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis cache set error: {e}")

    async def calculate_redemption_value(
        self,
        client_id: str,
        redemption_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cabin_class: Optional[str] = None,
        airline_codes: Optional[List[str]] = None,
        limit: int = 100
    ) -> RedemptionValueSummary:
        """
        Calculate redemption values with high performance and mechanical sympathy.
        Uses caching, batch processing, and efficient data structures.
        """
        start_time = datetime.utcnow()

        # Build cache key based on all parameters for maximum cache hit rate
        cache_key_parts = [
            "redemption_value",
            client_id,
            redemption_id or "all",
            start_date or "all",
            end_date or "all",
            cabin_class or "all",
            "|".join(airline_codes) if airline_codes else "all",
            str(limit)
        ]
        cache_key = ":".join(cache_key_parts)

        # Try to get from cache first (mechanical sympathy - cache is faster than DB)
        cached_result = await self._get_cache(cache_key)
        if cached_result:
            logger.info(f"Cache hit for client {client_id}")
            return RedemptionValueSummary(**cached_result)

        logger.info(f"Cache miss for client {client_id}, calculating fresh")

        # In a real implementation, this would query the database
        # For this example, we'll simulate the calculation
        redemptions = await self._fetch_redemptions_from_db(
            client_id, redemption_id, start_date, end_date, cabin_class, airline_codes, limit
        )

        if not redemptions:
            result = RedemptionValueSummary(
                client_id=client_id,
                total_redemptions=0,
                total_value=0.0,
                average_value=0.0,
                min_value=0.0,
                max_value=0.0,
                currency="USD",
                redemptions=[],
                calculated_at=datetime.utcnow().isoformat(),
                period_start=start_date,
                period_end=end_date
            )

            # Cache empty result to prevent repeated queries
            await self._set_cache(cache_key, result.dict(), CACHE_TTL_SHORT)
            return result

        # Calculate values in batch for maximum throughput
        calculated_redemptions = []
        total_value = 0.0
        values = []

        for redemption in redemptions:
            value = self._calculate_single_redemption_value(redemption)
            total_value += value
            values.append(value)

            response = RedemptionValueResponse(
                client_id=client_id,
                redemption_id=redemption.get('id'),
                booking_reference=redemption.get('booking_reference'),
                flight_details=redemption.get('flight_details', {}),
                redemption_value=value,
                currency="USD",
                redemption_date=redemption.get('redemption_date'),
                cabin_class=redemption.get('cabin_class'),
                airline=redemption.get('airline'),
                distance=redemption.get('distance', 0),
                fare_basis=redemption.get('fare_basis'),
                status=redemption.get('status'),
                calculated_at=datetime.utcnow().isoformat(),
                metadata=redemption.get('metadata', {})
            )
            calculated_redemptions.append(response)

        # Calculate statistics
        avg_value = total_value / len(calculated_redemptions) if calculated_redemptions else 0.0
        min_value = min(values) if values else 0.0
        max_value = max(values) if values else 0.0

        result = RedemptionValueSummary(
            client_id=client_id,
            total_redemptions=len(calculated_redemptions),
            total_value=round(total_value, 2),
            average_value=round(avg_value, 2),
            min_value=round(min_value, 2),
            max_value=round(max_value, 2),
            currency="USD",
            redemptions=calculated_redemptions,
            calculated_at=datetime.utcnow().isoformat(),
            period_start=start_date,
            period_end=end_date
        )

        # Cache the result for future requests
        await self._set_cache(cache_key, result.dict(), CACHE_TTL_MEDIUM)

        latency = (datetime.utcnow() - start_time).total_seconds()
        await performance_monitor.record_request(latency)

        logger.info(f"Calculated {len(calculated_redemptions)} redemptions for client {client_id} in {latency:.4f}s")
        return result

    def _calculate_single_redemption_value(self, redemption: Dict) -> float:
        """
        Calculate value for a single redemption using mechanical sympathy.
        This is a simplified version - real implementation would use actual award charts.
        """
        try:
            distance = redemption.get('distance', 0)
            cabin_class = redemption.get('cabin_class', 'ECONOMY').upper()

            # Base value per mile (simplified - real system would use award charts)
            base_values = {
                'ECONOMY': 0.01,
                'PREMIUM_ECONOMY': 0.015,
                'BUSINESS': 0.025,
                'FIRST': 0.04
            }

            base_value = base_values.get(cabin_class, 0.01)
            value = distance * base_value

            # Adjust for airline partnerships and other factors
            airline = redemption.get('airline', '').upper()
            if airline in ['AA', 'DL', 'UA']:  # Major US airlines
                value *= 1.1  # 10% bonus for partner airlines
            elif airline in ['BA', 'JL', 'QF']:  # Other major partners
                value *= 1.05

            # Round to 2 decimal places
            return round(value, 2)
        except Exception as e:
            logger.error(f"Error calculating redemption value: {e}")
            return 0.0

    async def _fetch_redemptions_from_db(
        self,
        client_id: str,
        redemption_id: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        cabin_class: Optional[str],
        airline_codes: Optional[List[str]],
        limit: int
    ) -> List[Dict]:
        """
        Fetch redemptions from database with mechanical sympathy.
        In a real implementation, this would use SQLAlchemy async queries.
        """
        await performance_monitor.record_db_query()

        # Simulate database query with realistic data
        # In production, this would be an async SQLAlchemy query
        logger.info(f"Querying database for client {client_id}")

        # Simulated data - replace with actual database query in production
        simulated_redemptions = [
            {
                'id': f'redempt_{i}',
                'booking_reference': f'BK-{client_id}-{i:06d}',
                'flight_details': {
                    'flight_number': f'FL-{i:04d}',
                    'departure': 'JFK',
                    'arrival': 'LAX',
                    'departure_time': '2024-01-15T08:00:00Z',
                    'arrival_time': '2024-01-15T11:30:00Z'
                },
                'redemption_date': '2024-01-15',
                'cabin_class': cabin_class or ['ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST'][i % 4],
                'airline': ['AA', 'DL', 'UA', 'BA', 'JL', 'QF'][i % 6],
                'distance': 2475 + (i * 100),
                'fare_basis': f'Y{i % 10}',
                'status': 'COMPLETED',
                'metadata': {'booking_class': 'Award', 'seats': 1}
            }
            for i in range(1, min(limit + 1, 1001))
        ]

        # Apply filters
        if start_date:
            simulated_redemptions = [
                r for r in simulated_redemptions
                if r['redemption_date'] >= start_date
            ]

        if end_date:
            simulated_redemptions = [
                r for r in simulated_redemptions
                if r['redemption_date'] <= end_date
            ]

        if cabin_class:
            simulated_redemptions = [
                r for r in simulated_redemptions
                if r['cabin_class'].upper() == cabin_class.upper()
            ]

        if airline_codes:
            simulated_redemptions = [
                r for r in simulated_redemptions
                if r['airline'].upper() in [code.upper() for code in airline_codes]
            ]

        if redemption_id:
            simulated_redemptions = [
                r for r in simulated_redemptions
                if r['id'] == redemption_id
            ]

        return simulated_redemptions[:limit]

# FastAPI Application
app = FastAPI(
    title="Client Redemption Value Analytics API",
    description="High-performance API for calculating award flight redemption values",
    version="1.0.0",
    docs_url="/api/v1/redemption-value/docs",
    redoc_url="/api/v1/redemption-value/redoc",
    openapi_url="/api/v1/redemption-value/openapi.json"
)

# Initialize calculator
calculator = RedemptionValueCalculator()

@app.get(
    "/api/v1/redemption-value/{client_id}",
    response_model=RedemptionValueSummary,
    summary="Calculate redemption values for a client",
    response_description="Redemption value summary with detailed calculations"
)
async def get_redemption_values(
    client_id: str,
    redemption_id: Optional[str] = Query(None, description="Specific redemption ID"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    cabin_class: Optional[str] = Query(None, description="Filter by cabin class"),
    airline_codes: Optional[str] = Query(
        None,
        description="Comma-separated airline codes (e.g., AA,DL,UA)"
    ),
    limit: int = Query(100, description="Maximum number of results", ge=1, le=1000)
):
    """
    Calculate the value of client redemptions based on award flight bookings.

    This endpoint provides insights on client redemption patterns and preferences
    by calculating the monetary value of each redemption.
    """
    try:
        # Parse airline codes
        parsed_airline_codes = None
        if airline_codes:
            parsed_airline_codes = [code.strip() for code in airline_codes.split(',') if code.strip()]

        result = await calculator.calculate_redemption_value(
            client_id=client_id,
            redemption_id=redemption_id,
            start_date=start_date,
            end_date=end_date,
            cabin_class=cabin_class,
            airline_codes=parsed_airline_codes,
            limit=limit
        )

        return result
    except Exception as e:
        logger.error(f"Error processing request for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating redemption values: {str(e)}"
        )

@app.get(
    "/api/v1/redemption-value/{client_id}/metrics",
    summary="Get performance metrics for redemption value calculations",
    response_description="Performance metrics and statistics"
)
async def get_metrics():
    """Get performance monitoring metrics for the redemption value API"""
    metrics = await performance_monitor.get_metrics()

    # Calculate average latency
    avg_latency = metrics['total_latency'] / metrics['request_count'] if metrics['request_count'] > 0 else 0

    return {
        "metrics": metrics,
        "average_latency_seconds": round(avg_latency, 6),
        "cache_hit_rate": metrics['cache_hits'] / (metrics['cache_hits'] + metrics['cache_misses'])
                         if (metrics['cache_hits'] + metrics['cache_misses']) > 0 else 0,
        "requests_per_second": metrics['request_count'] / max(
            (datetime.utcnow() - metrics['last_reset']).total_seconds(), 1
        )
    }

@app.post(
    "/api/v1/redemption-value/refresh-cache",
    summary="Refresh cache for a specific client",
    response_description="Cache refresh status"
)
async def refresh_cache(
    client_id: str,
    background_tasks: BackgroundTasks
):
    """Background task to refresh cache for a specific client"""
    background_tasks.add_task(calculator._set_cache, f"redemption_value:{client_id}:all:all:all:all:all:100", {}, 1)
    return {"status": "cache refresh scheduled", "client_id": client_id}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "redemption-value-api"}

# Performance monitoring middleware
@app.middleware("http")
async def add_performance_headers(request, call_next):
    """Add performance headers to each response with mechanical sympathy"""
    start_time = datetime.utcnow()

    response = await call_next(request)

    process_time = (datetime.utcnow() - start_time).total_seconds()
    response.headers["X-Process-Time-Seconds"] = f"{process_time:.4f}"
    response.headers["X-Request-ID"] = request.headers.get("x-request-id", "unknown")

    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "redemption_value_api:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,
        log_level="info"
    )
