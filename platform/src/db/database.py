"""
Database layer for District Award Travel
SQLite-based with async support for scalability
"""

import sqlite3
import asyncio
from typing import Optional, List, Dict, Any
import logging
from contextlib import asynccontextmanager
import aiosqlite

# Configure logging
logger = logging.getLogger(__name__)

# Database schema
SCHEMA = """
-- Bookings table
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    return_date TEXT,
    cabin_class TEXT NOT NULL,
    award_points INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_flight ON bookings(flight_number);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(departure_date);

-- Valuation cache
CREATE TABLE IF NOT EXISTS valuation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_number TEXT NOT NULL,
    cabin_class TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    return_date TEXT,
    base_value REAL NOT NULL,
    award_points INTEGER NOT NULL,
    multiplier REAL NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(flight_number, cabin_class, departure_date, return_date)
);

-- Indexes for valuation cache
CREATE INDEX IF NOT EXISTS idx_valuation_flight ON valuation_cache(flight_number);
CREATE INDEX IF NOT EXISTS idx_valuation_date ON valuation_cache(departure_date);
"""

class Database:
    """Async database connection manager"""

    def __init__(self, db_path: str = "platform/data/travel.db"):
        self.db_path = db_path
        self._connection = None

    async def initialize(self):
        """Initialize database with schema"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()
        logger.info("Database initialized with schema")

    async def get_connection(self):
        """Get a new database connection"""
        return await aiosqlite.connect(self.db_path)

    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None

# Global database instance
db = Database()

async def get_db():
    """Dependency to get database connection"""
    async with db.get_connection() as conn:
        yield conn

# Business logic methods
async def create_booking(conn: aiosqlite.Connection, booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new booking"""
    query = """
    INSERT INTO bookings
    (user_id, flight_number, departure_date, return_date, cabin_class, award_points, status, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        booking_data['user_id'],
        booking_data['flight_number'],
        booking_data['departure_date'],
        booking_data.get('return_date'),
        booking_data['cabin_class'],
        booking_data['award_points'],
        booking_data.get('status', 'pending'),
        booking_data.get('metadata', '{}')
    )

    cursor = await conn.execute(query, params)
    await conn.commit()
    booking_id = cursor.lastrowid

    # Return the created booking
    result = await conn.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,)
    )
    row = await result.fetchone()
    columns = [column[0] for column in result.description]
    return dict(zip(columns, row))

async def get_booking(conn: aiosqlite.Connection, booking_id: int) -> Optional[Dict[str, Any]]:
    """Get a booking by ID"""
    result = await conn.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,)
    )
    row = await result.fetchone()
    if not row:
        return None
    columns = [column[0] for column in result.description]
    return dict(zip(columns, row))

async def get_bookings(conn: aiosqlite.Connection, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get list of bookings with pagination"""
    result = await conn.execute(
        "SELECT * FROM bookings ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = await result.fetchall()
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in rows]

async def update_booking(conn: aiosqlite.Connection, booking_id: int, booking_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an existing booking"""
    # Build update query dynamically
    set_clauses = []
    params = []

    for key, value in booking_data.items():
        if key not in ['id', 'created_at']:
            set_clauses.append(f"{key} = ?")
            params.append(value)

    params.append(booking_id)
    query = f"""
    UPDATE bookings
    SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """

    await conn.execute(query, params)
    await conn.commit()

    # Return updated booking
    return await get_booking(conn, booking_id)

async def delete_booking(conn: aiosqlite.Connection, booking_id: int) -> bool:
    """Delete a booking"""
    await conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    await conn.commit()
    return True

async def get_user_bookings(conn: aiosqlite.Connection, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get all bookings for a specific user"""
    result = await conn.execute(
        "SELECT * FROM bookings WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = await result.fetchall()
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in rows]

async def cache_valuation(conn: aiosqlite.Connection, valuation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Cache a valuation result"""
    query = """
    INSERT OR REPLACE INTO valuation_cache
    (flight_number, cabin_class, departure_date, return_date, base_value, award_points, multiplier, calculated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        valuation_data['flight_number'],
        valuation_data['cabin_class'],
        valuation_data['departure_date'],
        valuation_data.get('return_date'),
        valuation_data['base_value'],
        valuation_data['award_points'],
        valuation_data['multiplier'],
        valuation_data.get('calculated_at', datetime.utcnow().isoformat())
    )

    await conn.execute(query, params)
    await conn.commit()

    # Return cached valuation
    result = await conn.execute(
        "SELECT * FROM valuation_cache WHERE flight_number = ? AND cabin_class = ? AND departure_date = ?",
        (valuation_data['flight_number'], valuation_data['cabin_class'], valuation_data['departure_date'])
    )
    row = await result.fetchone()
    columns = [column[0] for column in result.description]
    return dict(zip(columns, row))

async def get_cached_valuation(conn: aiosqlite.Connection, flight_number: str, cabin_class: str, departure_date: str) -> Optional[Dict[str, Any]]:
    """Get cached valuation"""
    result = await conn.execute(
        "SELECT * FROM valuation_cache WHERE flight_number = ? AND cabin_class = ? AND departure_date = ?",
        (flight_number, cabin_class, departure_date)
    )
    row = await result.fetchone()
    if not row:
        return None
    columns = [column[0] for column in result.description]
    return dict(zip(columns, row))

# Initialize database on import
async def init_db():
    """Initialize database on application startup"""
    await db.initialize()

# Run initialization
asyncio.run(init_db())
