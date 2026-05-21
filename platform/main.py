"""
District Award Travel - AI-Powered Award Travel Assistant
Main application entry point with FastAPI and distributed components
"""

import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator
from platform.src.pipeline import pipeline_router
from platform.src.intelligence import ai_router
from platform.src.api import api_router
from platform.src.observability import setup_observability
from platform.src.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="District Award Travel - AI Assistant",
    description="AI-powered award travel recommendation and support system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Setup observability
setup_observability(app)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="platform/public/static"), name="static")
templates = Jinja2Templates(directory="platform/public/templates")

# Include routers
app.include_router(api_router)
app.include_router(pipeline_router)
app.include_router(ai_router)

# Initialize database
init_db()

# Setup Prometheus metrics
Instrumentator().instrument(app).expose(app)

@app.get("/")
async def root(request: Request):
    """Main landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "district-award-travel-ai"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "platform.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "development") == "development",
        workers=int(os.getenv("WORKERS", 4))
    )
