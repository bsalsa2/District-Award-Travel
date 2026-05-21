"""
Award inventory and search API endpoints.
Handles award availability, search, and redemption calculations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import sqlite3
import os
from datetime import datetime, timedelta
from pydantic import BaseModel
from .users import get_current_user

# Database path
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "district_award_travel.db")

router = APIRouter(prefix="/api/awards", tags=["awards"])

class AwardSearchParams(BaseModel):
    departure_airport: Optional[str] = None
    arrival_airport: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    cabin_class: Optional[str] = None
    max_points: Optional[int] = None
    limit: int = 20

class AwardAvailability(BaseModel):
    id: int
    airline: str
    departure_airport: str
    arrival_airport: str
    departure_date: str
    arrival_date: str
    cabin_class: str
    points_required: int
    available_seats: int
    flight_number: str
    duration_hours: float
    departure_time: str
    arrival_time: str

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/search")
async def search_awards(
    departure_airport: Optional[str] = Query(None, description="Departure airport IATA code"),
    arrival_airport: Optional[str] = Query(None, description="Arrival airport IATA code"),
    departure_date: Optional[str] = Query(None, description="Departure date in YYYY-MM-DD format"),
    return_date: Optional[str] = Query(None, description="Return date in YYYY-MM-DD format"),
    cabin_class: Optional[str] = Query(None, description="Cabin class (economy, premium_economy, business, first)"),
    max_points: Optional[int] = Query(None, description="Maximum points to spend"),
    limit: int = Query(20, description="Maximum number of results to return"),
    current_user: dict = Depends(get_current_user)
):
    """Search for available award flights."""
    conn = get_db_connection()

    # Base query
    query = """
    SELECT ai.id, a.name as airline, ai.departure_airport_id, ai.arrival_airport_id,
           ai.departure_date, ai.arrival_date, ai.cabin_class, ai.award_points as points_required,
           ai.available_seats, ai.flight_number, ai.duration_minutes,
           dep.name as departure_airport, arr.name as arrival_airport,
           dep.iata_code as departure_iata, arr.iata_code as arrival_iata
    FROM award_inventory ai
    JOIN airlines a ON ai.airline_id = a.id
    JOIN airports dep ON ai.departure_airport_id = dep.id
    JOIN airports arr ON ai.arrival_airport_id = arr.id
    WHERE ai.available_seats > 0
    """

    params = []

    # Add filters
    if departure_airport:
        query += " AND dep.iata_code = ?"
        params.append(departure_airport)

    if arrival_airport:
        query += " AND arr.iata_code = ?"
        params.append(arrival_airport)

    if departure_date:
        query += " AND ai.departure_date = ?"
        params.append(departure_date)

    if cabin_class:
        query += " AND ai.cabin_class = ?"
        params.append(cabin_class)

    if max_points:
        query += " AND ai.award_points <= ?"
        params.append(max_points)

    query += " ORDER BY ai.award_points ASC LIMIT ?"
    params.append(limit)

    # Execute query
    results = conn.execute(query, params).fetchall()
    conn.close()

    # Format results
    awards = []
    for row in results:
        awards.append({
            "id": row["id"],
            "airline": row["airline"],
            "departure_airport": row["departure_airport"],
            "arrival_airport": row["arrival_airport"],
            "departure_iata": row["departure_iata"],
            "arrival_iata": row["arrival_iata"],
            "departure_date": row["departure_date"],
            "arrival_date": row["arrival_date"],
            "cabin_class": row["cabin_class"],
            "points_required": row["points_required"],
            "available_seats": row["available_seats"],
            "flight_number": row["flight_number"],
            "duration_hours": round(row["duration_minutes"] / 60, 1),
            "departure_time": row["departure_date"],
            "arrival_time": row["arrival_date"]
        })

    return {"results": awards, "count": len(awards)}

@router.get("/destinations")
async def get_popular_destinations(limit: int = 10):
    """Get popular award destinations."""
    conn = get_db_connection()

    query = """
    SELECT arr.iata_code, arr.name as destination, arr.city, arr.country, COUNT(*) as availability_count
    FROM award_inventory ai
    JOIN airports arr ON ai.arrival_airport_id = arr.id
    WHERE ai.available_seats > 0
    GROUP BY arr.iata_code
    ORDER BY availability_count DESC
    LIMIT ?
    """

    results = conn.execute(query, (limit,)).fetchall()
    conn.close()

    return {
        "destinations": [
            {
                "iata_code": row["iata_code"],
                "name": row["destination"],
                "city": row["city"],
                "country": row["country"],
                "availability_count": row["availability_count"]
            } for row in results
        ]
    }

@router.get("/{award_id}")
async def get_award_details(award_id: int, current_user: dict = Depends(get_current_user)):
    """Get detailed information about a specific award."""
    conn = get_db_connection()

    award = conn.execute(
        """SELECT ai.id, a.name as airline, a.iata_code as airline_iata,
        ai.departure_airport_id, ai.arrival_airport_id,
        ai.departure_date, ai.arrival_date, ai.cabin_class,
        ai.award_points as points_required, ai.available_seats,
        ai.flight_number, ai.duration_minutes,
        dep.name as departure_airport, dep.iata_code as departure_iata,
        arr.name as arrival_airport, arr.iata_code as arrival_iata
        FROM award_inventory ai
        JOIN airlines a ON ai.airline_id = a.id
        JOIN airports dep ON ai.departure_airport_id = dep.id
        JOIN airports arr ON ai.arrival_airport_id = arr.id
        WHERE ai.id = ? AND ai.available_seats > 0""",
        (award_id,)
    ).fetchone()

    conn.close()

    if not award:
        raise HTTPException(status_code=404, detail="Award not found or no longer available")

    return {
        "id": award["id"],
        "airline": award["airline"],
        "airline_iata": award["airline_iata"],
        "departure_airport": award["departure_airport"],
        "arrival_airport": award["arrival_airport"],
        "departure_iata": award["departure_iata"],
        "arrival_iata": award["arrival_iata"],
        "departure_date": award["departure_date"],
        "arrival_date": award["arrival_date"],
        "cabin_class": award["cabin_class"],
        "points_required": award["points_required"],
        "available_seats": award["available_seats"],
        "flight_number": award["flight_number"],
        "duration_hours": round(award["duration_minutes"] / 60, 1)
    }

@router.get("/user/available")
async def get_user_available_awards(current_user: dict = Depends(get_current_user)):
    """Get awards that the user can afford with their current points balance."""
    conn = get_db_connection()

    # Get user points
    points = conn.execute(
        "SELECT total_points FROM user_points WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    if not points:
        conn.close()
        raise HTTPException(status_code=404, detail="User points record not found")

    user_points = points["total_points"]

    # Get awards the user can afford
    awards = conn.execute(
        """SELECT ai.id, a.name as airline, ai.departure_airport_id,
        ai.arrival_airport_id, ai.departure_date, ai.arrival_date,
        ai.cabin_class, ai.award_points as points_required,
        ai.available_seats, ai.flight_number, ai.duration_minutes,
        dep.name as departure_airport, arr.name as arrival_airport,
        dep.iata_code as departure_iata, arr.iata_code as arrival_iata
        FROM award_inventory ai
        JOIN airlines a ON ai.airline_id = a.id
        JOIN airports dep ON ai.departure_airport_id = dep.id
        JOIN airports arr ON ai.arrival_airport_id = arr.id
        WHERE ai.available_seats > 0 AND ai.award_points <= ?
        ORDER BY ai.award_points ASC""",
        (user_points,)
    ).fetchall()

    conn.close()

    return {
        "points_balance": user_points,
        "affordable_awards": [
            {
                "id": row["id"],
                "airline": row["airline"],
                "departure_airport": row["departure_airport"],
                "arrival_airport": row["arrival_airport"],
                "departure_iata": row["departure_iata"],
                "arrival_iata": row["arrival_iata"],
                "departure_date": row["departure_date"],
                "arrival_date": row["arrival_date"],
                "cabin_class": row["cabin_class"],
                "points_required": row["points_required"],
                "available_seats": row["available_seats"],
                "flight_number": row["flight_number"],
                "duration_hours": round(row["duration_minutes"] / 60, 1)
            } for row in awards
        ]
    }
