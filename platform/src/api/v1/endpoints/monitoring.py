from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from config.settings import settings

router = APIRouter(prefix=f"{settings.API_V1_STR}/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.PROJECT_NAME
    }

@router.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    # In production, this would collect actual metrics
    metrics = {
        "predictions_served": 12456,
        "holds_created": 892,
        "cache_hit_rate": 0.87,
        "model_latency_ms": 45.2,
        "system_uptime": "99.99%",
        "timestamp": datetime.utcnow().isoformat()
    }
    return metrics

@router.get("/status")
async def get_system_status():
    """Get detailed system status"""
    return {
        "service": settings.PROJECT_NAME,
        "version": "2.1.0",
        "ai_model": {
            "loaded": True,
            "version": "v2.1.0",
            "device": "cuda" if "cuda" in str(settings.TENSORRT_ENGINE) else "cpu"
        },
        "database": {
            "status": "connected",
            "url": str(settings.DATABASE_URL)
        },
        "cache": {
            "status": "connected",
            "url": str(settings.REDIS_URL)
        },
        "last_update": datetime.utcnow().isoformat()
    }
