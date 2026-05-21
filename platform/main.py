"""
Main entry point for District Award Travel platform.
Orchestrates FastAPI app, database, and background services.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlite3
import os
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "district_award_travel.db")

def init_db():
    """Initialize database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # User profiles (award travel preferences)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        frequent_flyer_number TEXT,
        loyalty_program TEXT,
        preferred_cabin TEXT DEFAULT 'economy',
        home_airport TEXT,
        travel_style TEXT DEFAULT 'leisure',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Airlines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS airlines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        iata_code TEXT UNIQUE NOT NULL,
        alliance TEXT,
        website TEXT
    )
    """)

    # Airports
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS airports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        iata_code TEXT UNIQUE NOT NULL,
        city TEXT NOT NULL,
        country TEXT NOT NULL,
        latitude REAL,
        longitude REAL
    )
    """)

    # Award inventory (what's available to book)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS award_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        airline_id INTEGER NOT NULL,
        departure_airport_id INTEGER NOT NULL,
        arrival_airport_id INTEGER NOT NULL,
        departure_date TEXT NOT NULL,
        arrival_date TEXT NOT NULL,
        cabin_class TEXT NOT NULL,
        award_points INTEGER NOT NULL,
        available_seats INTEGER DEFAULT 0,
        flight_number TEXT,
        duration_minutes INTEGER,
        FOREIGN KEY (airline_id) REFERENCES airlines(id),
        FOREIGN KEY (departure_airport_id) REFERENCES airports(id),
        FOREIGN KEY (arrival_airport_id) REFERENCES airports(id)
    )
    """)

    # Bookings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        award_inventory_id INTEGER NOT NULL,
        booking_reference TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'confirmed',
        booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        redemption_date TIMESTAMP,
        points_used INTEGER NOT NULL,
        passengers INTEGER DEFAULT 1,
        special_requests TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (award_inventory_id) REFERENCES award_inventory(id)
    )
    """)

    # User points
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        total_points INTEGER DEFAULT 0,
        earned_points INTEGER DEFAULT 0,
        redeemed_points INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Points transactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS points_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        points INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,  -- 'earn', 'redeem', 'adjustment'
        description TEXT,
        related_booking_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (related_booking_id) REFERENCES bookings(id)
    )
    """)

    # Notifications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

# Initialize database
init_db()

# Lifespan for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing District Award Travel platform...")
    yield
    # Shutdown
    logger.info("Shutting down District Award Travel platform...")

# Create FastAPI app
app = FastAPI(
    title="District Award Travel API",
    description="API for award travel booking and redemption",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="platform/public/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="platform/public/templates")

# Include API routers
from platform.src.api import users, awards, bookings, points, search
app.include_router(users.router)
app.include_router(awards.router)
app.include_router(bookings.router)
app.include_router(points.router)
app.include_router(search.router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "District Award Travel"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
