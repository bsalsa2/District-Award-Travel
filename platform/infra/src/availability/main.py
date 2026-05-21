# -*- coding: utf-8 -*-
# FILE: platform/infra/src/availability/main.py

import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import redis
import psycopg2
from psycopg2 import pool
from prometheus_client import Counter, Gauge, generate_latest, REGISTRY
from pythonjsonlogger import jsonlogger
import aiohttp
import asyncio
from typing import Optional, List, Dict
import json
from datetime import datetime, timedelta

# Initialize FastAPI app
app = FastAPI(
    title="District Award Travel - Availability API",
    description="Global edge computing network for real-time award availability",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure logging
log_handler = logging.StreamHandler()
log_formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
log_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Metrics
REQUEST_COUNT = Counter(
    'availability_requests_total',
    'Total number of requests',
    ['endpoint', 'method', 'status']
)
REQUEST_LATENCY = Gauge(
    'availability_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)
CACHE_HITS = Counter(
    'availability_cache_hits_total',
    'Total number of cache hits'
)
CACHE_MISSES = Counter(
    'availability_cache_misses_total',
    'Total number of cache misses'
)
AWARD_UPDATES = Counter(
    'availability_award_updates_total',
    'Total number of award updates processed'
)

# Database connection pool
db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv("POSTGRES_HOST", "postgres-db"),
    database=os.getenv("POSTGRES_DB", "district_award"),
    user=os.getenv("POSTGRES_USER", "district"),
    password=os.getenv("POSTGRES_PASSWORD", "awardtravel"),
    port="5432"
)

# Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis-cache"),
    port=6379,
    decode_responses=True,
    socket_timeout=5
)

# Edge AI client
EDGE_AI_ENDPOINT = os.getenv("EDGE_AI_ENDPOINT", "http://edge-ai-service:8001")

class AwardRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    cabin_class: str = "economy"
    passengers: int = 1
    currency: str = "USD"

class AwardUpdate(BaseModel):
    award_id: str
    availability: bool
    price: Optional[float] = None
    seats: Optional[int] = None
    expires_at: str
    last_updated: str

# Helper functions
async def call_edge_ai(data: Dict) -> Dict:
    """Call NVIDIA Edge AI for real-time predictions"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EDGE_AI_ENDPOINT}/v2/models/availability/infer",
                json=data,
                timeout=2.0
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"prediction": None, "confidence": 0.0}
    except Exception as e:
        logger.error(f"Edge AI call failed: {str(e)}")
        return {"prediction": None, "confidence": 0.0}

def get_db_connection():
    """Get database connection from pool"""
    try:
        return db_pool.getconn()
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Database connection error")

def release_db_connection(conn):
    """Release database connection back to pool"""
    try:
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Database connection release failed: {str(e)}")

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    REQUEST_COUNT.labels(endpoint="/health", method="GET", status="200").inc()
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    REQUEST_COUNT.labels(endpoint="/metrics", method="GET", status="200").inc()
    return generate_latest(REGISTRY), 200

@app.post("/awards/search")
async def search_awards(request: AwardRequest):
    """Search for award availability"""
    start_time = datetime.utcnow()

    try:
        # Create cache key
        cache_key = f"award:{request.origin}:{request.destination}:{request.departure_date}:{request.cabin_class}"

        # Try to get from cache
        cached_data = redis_client.get(cache_key)
        if cached_data:
            CACHE_HITS.inc()
            logger.info(f"Cache hit for {cache_key}")
            return json.loads(cached_data)

        CACHE_MISSES.inc()

        # Get from database
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT award_id, availability, price, seats, expires_at, last_updated
                    FROM award_availability
                    WHERE origin = %s AND destination = %s AND departure_date = %s
                    AND cabin_class = %s AND passengers <= %s
                    ORDER BY last_updated DESC
                    LIMIT 100
                """
                cursor.execute(query, (
                    request.origin,
                    request.destination,
                    request.departure_date,
                    request.cabin_class,
                    request.passengers
                ))
                rows = cursor.fetchall()

                awards = []
                for row in rows:
                    awards.append({
                        "award_id": row[0],
                        "availability": row[1],
                        "price": row[2],
                        "seats": row[3],
                        "expires_at": row[4].isoformat() if row[4] else None,
                        "last_updated": row[5].isoformat()
                    })

                # Cache for 30 seconds
                redis_client.setex(cache_key, 30, json.dumps(awards))

                REQUEST_LATENCY.labels(endpoint="/awards/search").set(
                    (datetime.utcnow() - start_time).total_seconds()
                )
                REQUEST_COUNT.labels(endpoint="/awards/search", method="POST", status="200").inc()

                return {"awards": awards, "timestamp": datetime.utcnow().isoformat()}

        finally:
            release_db_connection(conn)

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        REQUEST_COUNT.labels(endpoint="/awards/search", method="POST", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/awards/update")
async def update_award_availability(update: AwardUpdate):
    """Update award availability"""
    try:
        # Validate expires_at
        try:
            expires_at = datetime.fromisoformat(update.expires_at)
        except ValueError:
            expires_at = datetime.utcnow() + timedelta(hours=24)

        # Update database
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO award_availability
                    (award_id, origin, destination, departure_date, cabin_class, passengers,
                     availability, price, seats, expires_at, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (award_id) DO UPDATE SET
                        availability = EXCLUDED.availability,
                        price = EXCLUDED.price,
                        seats = EXCLUDED.seats,
                        expires_at = EXCLUDED.expires_at,
                        last_updated = EXCLUDED.last_updated
                    RETURNING award_id
                """
                cursor.execute(query, (
                    update.award_id,
                    "JFK",  # Would be extracted from award_id in real implementation
                    "LAX",  # Would be extracted from award_id in real implementation
                    "2026-06-01",  # Would be extracted from award_id in real implementation
                    "economy",
                    1,
                    update.availability,
                    update.price,
                    update.seats,
                    expires_at,
                    datetime.utcnow()
                ))
                award_id = cursor.fetchone()[0]

                # Invalidate cache
                cache_keys = [
                    f"award:JFK:LAX:2026-06-01:economy",
                    f"award:*"
                ]
                for key in cache_keys:
                    redis_client.delete(key)

                # Call Edge AI for prediction update
                edge_data = {
                    "award_id": update.award_id,
                    "availability": update.availability,
                    "price": update.price,
                    "seats": update.seats
                }
                await call_edge_ai(edge_data)

                AWARD_UPDATES.inc()
                logger.info(f"Updated award {update.award_id}")

                return {"status": "success", "award_id": award_id}

        finally:
            release_db_connection(conn)

    except Exception as e:
        logger.error(f"Update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/awards/realtime/{origin}/{destination}/{departure_date}")
async def realtime_availability(origin: str, destination: str, departure_date: str):
    """Get real-time availability with AI predictions"""
    start_time = datetime.utcnow()

    try:
        # Create cache key
        cache_key = f"realtime:{origin}:{destination}:{departure_date}"

        # Try to get from cache
        cached_data = redis_client.get(cache_key)
        if cached_data:
            CACHE_HITS.inc()
            logger.info(f"Cache hit for {cache_key}")
            return json.loads(cached_data)

        CACHE_MISSES.inc()

        # Get from database
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT award_id, availability, price, seats, expires_at, last_updated
                    FROM award_availability
                    WHERE origin = %s AND destination = %s AND departure_date = %s
                    ORDER BY last_updated DESC
                    LIMIT 50
                """
                cursor.execute(query, (origin, destination, departure_date))
                rows = cursor.fetchall()

                awards = []
                for row in rows:
                    awards.append({
                        "award_id": row[0],
                        "availability": row[1],
                        "price": row[2],
                        "seats": row[3],
                        "expires_at": row[4].isoformat() if row[4] else None,
                        "last_updated": row[5].isoformat()
                    })

                # Call Edge AI for real-time prediction
                edge_data = {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "awards": awards
                }
                ai_result = await call_edge_ai(edge_data)

                result = {
                    "awards": awards,
                    "ai_prediction": ai_result.get("prediction"),
                    "confidence": ai_result.get("confidence"),
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Cache for 10 seconds (real-time data)
                redis_client.setex(cache_key, 10, json.dumps(result))

                REQUEST_LATENCY.labels(endpoint="/awards/realtime").set(
                    (datetime.utcnow() - start_time).total_seconds()
                )
                REQUEST_COUNT.labels(endpoint="/awards/realtime", method="GET", status="200").inc()

                return result

        finally:
            release_db_connection(conn)

    except Exception as e:
        logger.error(f"Realtime availability failed: {str(e)}")
        REQUEST_COUNT.labels(endpoint="/awards/realtime", method="GET", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))

# Initialize database
def init_db():
    """Initialize database tables"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS award_availability (
                    award_id VARCHAR(50) PRIMARY KEY,
                    origin VARCHAR(10) NOT NULL,
                    destination VARCHAR(10) NOT NULL,
                    departure_date DATE NOT NULL,
                    cabin_class VARCHAR(20) NOT NULL,
                    passengers INTEGER NOT NULL,
                    availability BOOLEAN NOT NULL,
                    price DECIMAL(10,2),
                    seats INTEGER,
                    expires_at TIMESTAMP,
                    last_updated TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_award_availability_search
                ON award_availability (origin, destination, departure_date, cabin_class, passengers)
            """)

            conn.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_connection(conn)

# Initialize on startup
init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        timeout_keep_alive=60,
        log_config=None,
        access_log=False
    )
