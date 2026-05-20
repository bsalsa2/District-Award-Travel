import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import start_http_server, Counter, Gauge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics
UPDATE_COUNTER = Counter(
    'realtime_updates_total',
    'Total number of real-time updates processed'
)
UPDATE_LATENCY = Gauge(
    'realtime_update_latency_seconds',
    'Latency of real-time updates in seconds'
)
ACTIVE_CONNECTIONS = Gauge(
    'realtime_active_connections',
    'Number of active real-time connections'
)

app = FastAPI(title="District Award Travel Real-time Updater")

class UpdateData(BaseModel):
    table: str
    operation: str  # INSERT, UPDATE, DELETE
    data: Dict[str, Any]
    timestamp: datetime

# Database connection pool
db_pool: asyncpg.Pool = None
redis_client: redis.Redis = None

async def get_db_connection():
    """Get a database connection from the pool"""
    return await db_pool.acquire()

async def release_db_connection(conn):
    """Release a database connection back to the pool"""
    await db_pool.release(conn)

async def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=app.state.config.POSTGRES_HOST,
        port=app.state.config.POSTGRES_PORT,
        user=app.state.config.POSTGRES_USER,
        password=app.state.config.POSTGRES_PASSWORD,
        database=app.state.config.POSTGRES_DB,
        min_size=5,
        max_size=20
    )
    logger.info("Database connection pool initialized")

async def init_redis():
    """Initialize Redis client"""
    global redis_client
    redis_client = redis.Redis(
        host=app.state.config.REDIS_HOST,
        port=app.state.config.REDIS_PORT,
        decode_responses=True
    )
    logger.info("Redis client initialized")

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    # Load configuration from environment
    from pydantic import BaseSettings

    class Config(BaseSettings):
        POSTGRES_HOST: str
        POSTGRES_PORT: int
        POSTGRES_DB: str
        POSTGRES_USER: str
        POSTGRES_PASSWORD: str
        REDIS_HOST: str
        REDIS_PORT: int

        class Config:
            env_file = ".env"

    app.state.config = Config()

    # Initialize database and Redis
    await init_db_pool()
    await init_redis()

    # Start metrics server
    start_http_server(8000)
    logger.info("Real-time updater started and metrics server listening on port 8000")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")

@app.post("/update")
async def receive_update(update: UpdateData):
    """Receive a real-time update and process it"""
    start_time = datetime.now()

    try:
        # Validate the update
        if not update.table or not update.operation or not update.data:
            raise HTTPException(status_code=400, detail="Invalid update data")

        # Log the update
        logger.info(f"Received update for table {update.table}: {update.operation}")

        # Process the update based on operation type
        if update.operation == "INSERT":
            await process_insert(update.table, update.data)
        elif update.operation == "UPDATE":
            await process_update(update.table, update.data)
        elif update.operation == "DELETE":
            await process_delete(update.table, update.data)
        else:
            raise HTTPException(status_code=400, detail="Invalid operation type")

        # Publish the update to Redis for WebSocket distribution
        await publish_update(update)

        # Update metrics
        UPDATE_COUNTER.inc()
        UPDATE_LATENCY.set((datetime.now() - start_time).total_seconds())

        return {"status": "success", "message": "Update processed"}

    except Exception as e:
        logger.error(f"Error processing update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_insert(table: str, data: Dict[str, Any]):
    """Process an INSERT operation"""
    conn = await get_db_connection()
    try:
        columns = ', '.join(data.keys())
        values = ', '.join([f"${i+1}" for i in range(len(data))])
        query = f"INSERT INTO {table} ({columns}) VALUES ({values})"

        await conn.execute(query, *data.values())
        logger.debug(f"Inserted data into {table}")
    finally:
        await release_db_connection(conn)

async def process_update(table: str, data: Dict[str, Any]):
    """Process an UPDATE operation"""
    if 'id' not in data:
        raise ValueError("UPDATE operation requires an 'id' field")

    conn = await get_db_connection()
    try:
        set_clause = ', '.join([f"{k} = ${i+1}" for i, k in enumerate(data.keys()) if k != 'id'])
        query = f"UPDATE {table} SET {set_clause} WHERE id = ${len(data)}"

        values = [v for k, v in data.items() if k != 'id'] + [data['id']]
        await conn.execute(query, *values)
        logger.debug(f"Updated data in {table} with id {data['id']}")
    finally:
        await release_db_connection(conn)

async def process_delete(table: str, data: Dict[str, Any]):
    """Process a DELETE operation"""
    if 'id' not in data:
        raise ValueError("DELETE operation requires an 'id' field")

    conn = await get_db_connection()
    try:
        query = f"DELETE FROM {table} WHERE id = $1"
        await conn.execute(query, data['id'])
        logger.debug(f"Deleted data from {table} with id {data['id']}")
    finally:
        await release_db_connection(conn)

async def publish_update(update: UpdateData):
    """Publish the update to Redis for WebSocket distribution"""
    try:
        channel = f"updates:{update.table}"
        message = {
            "table": update.table,
            "operation": update.operation,
            "data": update.data,
            "timestamp": update.timestamp.isoformat()
        }

        await redis_client.publish(channel, json.dumps(message))
        logger.debug(f"Published update to channel {channel}")
    except Exception as e:
        logger.error(f"Error publishing update to Redis: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = await get_db_connection()
        await conn.execute("SELECT 1")
        await release_db_connection(conn)

        # Check Redis connection
        if redis_client:
            await redis_client.ping()

        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
