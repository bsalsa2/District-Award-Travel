import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool
import redis
from prometheus_client import make_wsgi_app, Counter, Gauge
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.requests import Request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv('DB_HOST', 'postgres'),
    port=os.getenv('DB_PORT', '5432'),
    dbname=os.getenv('DB_NAME', 'award_travel'),
    user=os.getenv('DB_USER', 'travel_admin'),
    password=os.getenv('DB_PASSWORD', 'securepassword')
)

# Redis connection
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    decode_responses=True
)

# Prometheus metrics
FLIGHT_SEARCH_COUNTER = Counter(
    'flight_search_total',
    'Total number of flight searches',
    ['origin', 'destination', 'cabin_class']
)

FLIGHT_AVAILABILITY_GAUGE = Gauge(
    'flight_availability_count',
    'Number of available flight awards',
    ['airline', 'cabin_class']
)

app = FastAPI(title="Flight Award Service", version="1.0.0")

# Add prometheus wsgi middleware to route /metrics requests
app.add_route("/metrics", WSGIMiddleware(make_wsgi_app()))

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    cabin_class: str = "economy"
    adults: int = 1
    children: int = 0
    infants: int = 0

class FlightAward(BaseModel):
    id: int
    airline: str
    airline_code: str
    origin: str
    destination: str
    cabin_class: str
    miles_required: int
    points_required: int
    booking_fee: float
    fuel_surcharge: float
    taxes: float
    total_cost: float
    currency: str
    valid_from: str
    valid_to: str
    airline_alliance: Optional[str] = None

def get_db_connection():
    """Get a database connection from the pool"""
    try:
        conn = db_pool.getconn()
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def release_db_connection(conn):
    """Release a database connection back to the pool"""
    try:
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error releasing database connection: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize the service on startup"""
    logger.info("Flight Award Service starting up...")
    # Initialize database schema if needed
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'flight_awards'
                )
            """)
            if not cursor.fetchone()[0]:
                logger.info("Initializing flight awards database...")
                with open('/app/init.sql', 'r') as f:
                    cursor.execute(f.read())
                conn.commit()
        release_db_connection(conn)
    except Exception as e:
        logger.error(f"Startup initialization error: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        release_db_connection(conn)

        # Check Redis connection
        redis_client.ping()

        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}, 500

@app.post("/search", response_model=List[FlightAward])
async def search_flight_awards(request: FlightSearchRequest):
    """Search for flight award options"""
    try:
        # Log the search
        logger.info(f"Flight search: {request.origin} to {request.destination} on {request.departure_date}")

        # Increment metrics
        FLIGHT_SEARCH_COUNTER.labels(
            origin=request.origin,
            destination=request.destination,
            cabin_class=request.cabin_class
        ).inc()

        # Check cache first
        cache_key = f"flight_search:{request.origin}:{request.destination}:{request.departure_date}:{request.cabin_class}"
        cached_result = redis_client.get(cache_key)
        if cached_result:
            logger.info("Returning cached flight search results")
            return eval(cached_result)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Base query for one-way flights
            query = """
                SELECT
                    fa.id, a.name as airline, a.code as airline_code,
                    orig.iata_code as origin, dest.iata_code as destination,
                    fa.cabin_class, fa.miles_required, fa.points_required,
                    fa.booking_fee, fa.fuel_surcharge, fa.taxes,
                    (fa.miles_required * 0.01 + fa.booking_fee + fa.fuel_surcharge + fa.taxes) as total_cost,
                    fa.currency, fa.valid_from, fa.valid_to, a.alliance as airline_alliance
                FROM flight_awards fa
                JOIN airlines a ON fa.airline_id = a.id
                JOIN airports orig ON fa.origin_airport_id = orig.id
                JOIN airports dest ON fa.destination_airport_id = dest.id
                WHERE orig.iata_code = %s
                AND dest.iata_code = %s
                AND fa.cabin_class = %s
                AND fa.is_active = TRUE
                AND CURRENT_DATE BETWEEN fa.valid_from AND fa.valid_to
            """

            params = [request.origin, request.destination, request.cabin_class]

            # Add date filtering if departure_date is provided
            if request.departure_date:
                departure_date = datetime.strptime(request.departure_date, "%Y-%m-%d").date()
                query += " AND fa.valid_from <= %s AND fa.valid_to >= %s"
                params.extend([departure_date, departure_date])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to FlightAward objects
            awards = []
            for row in rows:
                award = FlightAward(
                    id=row[0],
                    airline=row[1],
                    airline_code=row[2],
                    origin=row[3],
                    destination=row[4],
                    cabin_class=row[5],
                    miles_required=row[6],
                    points_required=row[7],
                    booking_fee=row[8],
                    fuel_surcharge=row[9],
                    taxes=row[10],
                    total_cost=row[11],
                    currency=row[12],
                    valid_from=row[13].isoformat(),
                    valid_to=row[14].isoformat(),
                    airline_alliance=row[15]
                )
                awards.append(award)

            # Cache the result for 5 minutes
            redis_client.setex(cache_key, 300, str(awards))

            # Update metrics
            FLIGHT_AVAILABILITY_GAUGE.labels(
                airline="all",
                cabin_class=request.cabin_class
            ).set(len(awards))

            return awards
    except Exception as e:
        logger.error(f"Flight search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            release_db_connection(conn)

@app.get("/awards/{award_id}", response_model=FlightAward)
async def get_flight_award(award_id: int):
    """Get details for a specific flight award"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    fa.id, a.name as airline, a.code as airline_code,
                    orig.iata_code as origin, dest.iata_code as destination,
                    fa.cabin_class, fa.miles_required, fa.points_required,
                    fa.booking_fee, fa.fuel_surcharge, fa.taxes,
                    (fa.miles_required * 0.01 + fa.booking_fee + fa.fuel_surcharge + fa.taxes) as total_cost,
                    fa.currency, fa.valid_from, fa.valid_to, a.alliance as airline_alliance
                FROM flight_awards fa
                JOIN airlines a ON fa.airline_id = a.id
                JOIN airports orig ON fa.origin_airport_id = orig.id
                JOIN airports dest ON fa.destination_airport_id = dest.id
                WHERE fa.id = %s AND fa.is_active = TRUE
            """, [award_id])

            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Flight award not found")

            award = FlightAward(
                id=row[0],
                airline=row[1],
                airline_code=row[2],
                origin=row[3],
                destination=row[4],
                cabin_class=row[5],
                miles_required=row[6],
                points_required=row[7],
                booking_fee=row[8],
                fuel_surcharge=row[9],
                taxes=row[10],
                total_cost=row[11],
                currency=row[12],
                valid_from=row[13].isoformat(),
                    valid_to=row[14].isoformat(),
                    airline_alliance=row[15]
            )

            return award
    except Exception as e:
        logger.error(f"Get flight award error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            release_db_connection(conn)

@app.get("/airlines")
async def get_airlines():
    """Get list of supported airlines"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, code, alliance FROM airlines ORDER BY name")
            rows = cursor.fetchall()

            airlines = []
            for row in rows:
                airlines.append({
                    "id": row[0],
                    "name": row[1],
                    "code": row[2],
                    "alliance": row[3]
                })

            return airlines
    except Exception as e:
        logger.error(f"Get airlines error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            release_db_connection(conn)

@app.get("/airports")
async def get_airports():
    """Get list of supported airports"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT iata_code, name, city, country FROM airports ORDER BY name")
            rows = cursor.fetchall()

            airports = []
            for row in rows:
                airports.append({
                    "iata_code": row[0],
                    "name": row[1],
                    "city": row[2],
                    "country": row[3]
                })

            return airports
    except Exception as e:
        logger.error(f"Get airports error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            release_db_connection(conn)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
