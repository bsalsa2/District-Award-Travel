"""
District Award Travel — Travel Booking Dashboard
Main FastAPI application entry point with integrated observability.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from platform.src.pipeline.booking_pipeline import BookingPipeline
from platform.src.intelligence.valuation_engine import ValuationEngine
from platform.src.api.routes import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Initialize FastAPI
app = FastAPI(
    title="District Award Travel Dashboard",
    description="Travel booking dashboard for award travel management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI for observability
FastAPIInstrumentor.instrument_app(app)
RequestsInstrumentor().instrument()

# Initialize business logic services
booking_pipeline = BookingPipeline()
valuation_engine = ValuationEngine()

# Mount static files
app.mount("/static", StaticFiles(directory="platform/public/static"), name="static")
templates = Jinja2Templates(directory="platform/public/templates")

# Include API routes
app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Main dashboard endpoint"""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "District Award Travel Dashboard",
            "bookings": await booking_pipeline.get_recent_bookings(limit=10),
            "valuation_metrics": valuation_engine.get_current_metrics()
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "district-award-travel"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return {"status": "metrics endpoint configured via prometheus-fastapi-instrumentator"}

if __name__ == "__main__":
    Instrumentator().instrument(app).expose(app)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        log_level="info"
    )
