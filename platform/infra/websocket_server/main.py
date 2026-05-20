import asyncio
import json
import logging
from datetime import datetime
from typing import Set

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from prometheus_client import start_http_server, Gauge
from starlette.websockets import WebSocketState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics
ACTIVE_WEBSOCKETS = Gauge(
    'websocket_active_connections',
    'Number of active WebSocket connections'
)
MESSAGE_COUNTER = Gauge(
    'websocket_messages_total',
    'Total number of WebSocket messages sent',
    ['type']
)

app = FastAPI(title="District Award Travel WebSocket Server")

# WebSocket connections
active_connections: Set[WebSocket] = set()

# Redis client
redis_client: redis.Redis = None

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
        REDIS_HOST: str
        REDIS_PORT: int

        class Config:
            env_file = ".env"

    app.state.config = Config()

    # Initialize Redis
    await init_redis()

    # Start metrics server
    start_http_server(8080)
    logger.info("WebSocket server started and metrics server listening on port 8080")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_connections.add(websocket)
    ACTIVE_WEBSOCKETS.inc()

    logger.info(f"New WebSocket connection. Total active: {len(active_connections)}")

    try:
        # Subscribe to Redis channels based on user roles (simplified)
        # In production, you'd authenticate the user and subscribe to appropriate channels
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(
            "updates:award_bookings",
            "updates:customer_data",
            "updates:inventory",
            "updates:flights"
        )

        # Start a background task to listen for Redis messages
        asyncio.create_task(handle_redis_messages(websocket, pubsub))

        # Keep the connection open
        while True:
            # You could implement ping/pong for connection health
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        active_connections.discard(websocket)
        ACTIVE_WEBSOCKETS.dec()
        await pubsub.unsubscribe()
        await pubsub.close()
        logger.info(f"WebSocket connection closed. Total active: {len(active_connections)}")

async def handle_redis_messages(websocket: WebSocket, pubsub):
    """Handle messages from Redis pub/sub"""
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                channel = message['channel']
                data = message['data']

                try:
                    # Parse the message
                    message_data = json.loads(data)

                    # Send the message to the WebSocket client
                    await websocket.send_json({
                        "type": "update",
                        "channel": channel,
                        "data": message_data,
                        "timestamp": datetime.now().isoformat()
                    })

                    MESSAGE_COUNTER.labels(type='update').inc()

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in Redis message: {data}")
                except Exception as e:
                    logger.error(f"Error processing Redis message: {str(e)}")

    except Exception as e:
        logger.error(f"Error in Redis message handler: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
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
