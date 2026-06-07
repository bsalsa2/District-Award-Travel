"""
Main FastAPI application for District Award Travel.
Central entry point with all API routes and dependencies.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from redis.asyncio import Redis
from platform.src.endpoints import award_availability
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="District Award Travel API",
    description="High-performance API for award flight availability",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(award_availability.router)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.state.redis = Redis.from_url(redis_url)
    logger.info("Redis connection established")

    # Test Redis connection
    try:
        await app.state.redis.ping()
        logger.info("Redis ping successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    if hasattr(app.state, "redis"):
        await app.state.redis.close()
        logger.info("Redis connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None
    )
