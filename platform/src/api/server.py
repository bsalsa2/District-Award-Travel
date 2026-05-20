"""
FastAPI backend for District Award Travel Award Search Engine.
High-performance API with optimized data structures and minimal latency.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta
import os
import random
import logging
from . import database, auth
from .database import AwardProgram, AwardResult, Client
from .auth import Token, User, UserCreate, get_current_active_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="District Award Travel API",
    description="High-performance award search engine backend",
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

# Include routers
from .routers import auth_router, client_router, award_router, pipeline_router

app.include_router(auth_router.router)
app.include_router(client_router.router)
app.include_router(award_router.router)
app.include_router(pipeline_router.router)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    database.init_db()
    logger.info("Database initialized")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "District Award Travel API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Generate realistic award data
def generate_award_data(origin: str, destination: str, cabin: str) -> List[dict]:
    """Generate realistic award search results."""
    airlines = [
        {"code": "AA", "name": "American Airlines", "alliance": "oneworld"},
        {"code": "DL", "name": "Delta Air Lines", "alliance": "SkyTeam"},
        {"code": "UA", "name": "United Airlines", "alliance": "Star Alliance"},
        {"code": "JL", "name": "Japan Airlines", "alliance": "oneworld"},
        {"code": "NH", "name": "ANA", "alliance": "Star Alliance"},
        {"code": "BA", "name": "British Airways", "alliance": "oneworld"},
        {"code": "EK", "name": "Emirates", "alliance": "SkyTeam"},
        {"code": "QF", "name": "Qantas", "alliance": "oneworld"},
    ]

    routes = [
        ("JFK", "NRT", "JFK↔NRT"),
        ("LAX", "HND", "LAX↔HND"),
        ("SFO", "NRT", "SFO↔NRT"),
        ("DFW", "HND", "DFW↔HND"),
        ("ORD", "NRT", "ORD↔NRT"),
        ("BOS", "HND", "BOS↔HND"),
        ("MIA", "NRT", "MIA↔NRT"),
        ("SEA", "HND", "SEA↔HND"),
    ]

    cabin_classes = ["Economy", "Premium Economy", "Business", "First"]

    # Filter by requested parameters
    filtered_routes = [r for r in routes if r[0] == origin and r[1] == destination]

    results = []
    for i, route in enumerate(filtered_routes[:10]):  # Limit to 10 results
        airline = random.choice(airlines)
        miles_range = {
            "Economy": (35000, 70000),
            "Premium Economy": (60000, 100000),
            "Business": (90000, 150000),
            "First": (120000, 200000)
        }

        min_miles, max_miles = miles_range.get(cabin, (50000, 100000))
        miles = random.randint(min_miles, max_miles)

        cash_value = random.uniform(800, 2500)
        cpp = (miles / cash_value) * 100

        # Determine verdict based on cpp
        if cpp < 5:
            verdict = "EXCELLENT"
        elif cpp < 8:
            verdict = "GOOD"
        elif cpp < 12:
            verdict = "FAIR"
        else:
            verdict = "SKIP"

        results.append({
            "airline": airline["name"],
            "airline_code": airline["code"],
            "route": route[2],
            "origin": route[0],
            "destination": route[1],
            "cabin_class": cabin,
            "miles_required": miles,
            "cash_value_usd": round(cash_value, 2),
            "cpp": round(cpp, 2),
            "verdict": verdict,
            "program_name": f"{airline['name']} AAdvantage" if airline["code"] == "AA" else
                           f"{airline['name']} SkyMiles" if airline["code"] == "DL" else
                           f"{airline['name']} MileagePlus" if airline["code"] == "UA" else
                           f"{airline['name']} Mileage Plan" if airline["code"] == "JL" else
                           f"{airline['name']} Mileage Club" if airline["code"] == "NH" else
                           f"{airline['name']} Executive Club" if airline["code"] == "BA" else
                           f"{airline['name']} Skywards" if airline["code"] == "EK" else
                           f"{airline['name']} Qantas Frequent Flyer",
            "alliance": airline["alliance"],
            "booking_url": f"https://book.{airline['code'].lower()}airlines.com/flights/{route[0]}-{route[1]}",
            "departure_date": "2026-06-15",
            "return_date": "2026-06-25"
        })

    return results

# Initialize database with sample programs
def init_sample_programs(db: Session):
    """Initialize database with sample airline programs."""
    programs = [
        {"airline": "American Airlines", "program_name": "AAdvantage", "alliance": "oneworld", "website": "https://www.aa.com/aadvantage"},
        {"airline": "Delta Air Lines", "program_name": "SkyMiles", "alliance": "SkyTeam", "website": "https://www.delta.com/skymiles"},
        {"airline": "United Airlines", "program_name": "MileagePlus", "alliance": "Star Alliance", "website": "https://www.united.com/mileageplus"},
        {"airline": "Japan Airlines", "program_name": "Mileage Plan", "alliance": "oneworld", "website": "https://www.jal.co.jp/en/jmb/"},
        {"airline": "ANA", "program_name": "Mileage Club", "alliance": "Star Alliance", "website": "https://www.ana.co.jp/en/wws/service/page/FP/150010000.html"},
        {"airline": "British Airways", "program_name": "Executive Club", "alliance": "oneworld", "website": "https://www.britishairways.com/en-us/executive-club"},
        {"airline": "Emirates", "program_name": "Skywards", "alliance": "SkyTeam", "website": "https://www.emirates.com/english/skywwards/"},
        {"airline": "Qantas", "program_name": "Qantas Frequent Flyer", "alliance": "oneworld", "website": "https://www.qantas.com/fflyer/dyn/program"},
    ]

    for program in programs:
        db_program = db.query(AwardProgram).filter(AwardProgram.airline == program["airline"]).first()
        if not db_program:
            db_program = AwardProgram(**program)
            db.add(db_program)
    db.commit()

@app.on_event("startup")
async def startup():
    """Initialize sample data on startup."""
    db = next(database.get_db())
    init_sample_programs(db)
