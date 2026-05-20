"""
FastAPI backend server for District Award Travel.
Optimized for high throughput with proper async handling and caching.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from typing import List, Optional

# Local imports
from . import models, schemas, database, auth
from .database import get_db

# Configure logging for performance monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="District Award Travel API",
    description="High-performance backend for award travel management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Configuration - optimized for GitHub Pages domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://district-award-travel.github.io",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routers import auth as auth_router
from .routers import clients as clients_router
from .routers import searches as searches_router
from .routers import intakes as intakes_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(clients_router.router, prefix="/api", tags=["clients"])
app.include_router(searches_router.router, prefix="/api", tags=["searches"])
app.include_router(intakes_router.router, prefix="/api", tags=["intakes"])

@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting District Award Travel API server")
    # Initialize database
    database.init_db()

@app.get("/")
async def root():
    """Root endpoint for health checks."""
    return {
        "service": "District Award Travel API",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={"status": "healthy"},
        status_code=200
    )

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Middleware to add processing time header."""
    start_time = datetime.utcnow()
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler for consistent error responses."""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Generic exception handler."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Initialize database on startup
database.init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=4  # Optimized for CPU-bound operations
    )
