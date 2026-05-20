import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.endpoints import predictions, monitoring
from config.settings import settings
from services.data_pipeline import DataPipeline
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Predictive Award Availability Engine with Generative AI Forecasting",
    version="2.1.0",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(predictions.router)
app.include_router(monitoring.router)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    logger.info("Starting District Award Travel Predictive Engine")

    # Start data pipeline as a background task
    asyncio.create_task(run_data_pipeline())

async def run_data_pipeline():
    """Run the data pipeline in the background"""
    pipeline = DataPipeline()
    await pipeline.run()

@app.get("/")
async def root():
    return {
        "message": "District Award Travel - Predictive Award Availability Engine",
        "version": "2.1.0",
        "documentation": f"{settings.API_V1_STR}/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=4
    )
