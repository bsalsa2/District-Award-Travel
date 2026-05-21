import asyncpg
from typing import List, Dict, Optional, Any
import logging
from ..config import config
from ..models.award import Award
from datetime import date
from time import perf_counter

logger = logging.getLogger(__name__)

class GPUDBAwardRepository:
    """
    Repository for interacting with GPU-accelerated database.
    Optimized for high-throughput award searches with vectorized operations.
    """

    def __init__(self):
        self.pool = None
        self.connected = False

    async def connect(self):
        """Establish connection to GPU database"""
        if self.connected:
            return

        try:
            self.pool = await asyncpg.create_pool(
                host=config.GPU_DB_HOST,
                port=config.GPU_DB_PORT,
                user=config.GPU_DB_USER,
                password=config.GPU_DB_PASSWORD,
                database=config.GPU_DB_DB,
                min_size=5,
                max_size=20,
                command_timeout=config.QUERY_TIMEOUT,
            )
            self.connected = True
            logger.info("Connected to GPU database successfully")
        except Exception as e:
            logger.error(f"Failed to connect to GPU database: {e}")
            self.connected = False
            raise

    async def close(self):
        """Close database connection"""
        if self.pool and self.connected:
            await self.pool.close()
            self.connected = False
            logger.info("GPU database connection closed")

    async def ensure_schema(self):
        """Ensure required tables and indexes exist"""
        if not self.connected:
            await self.connect()

        async with self.pool.acquire() as conn:
            # Create awards table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS awards_gpu (
                    id SERIAL PRIMARY KEY,
                    program_id INTEGER NOT NULL,
                    airline VARCHAR(10) NOT NULL,
                    flight_number VARCHAR(20),
                    departure_airport VARCHAR(3) NOT NULL,
                    arrival_airport VARCHAR(3) NOT NULL,
                    departure_date DATE NOT NULL,
                    arrival_date DATE NOT NULL,
                    cabin_class VARCHAR(20) NOT NULL,
                    award_type VARCHAR(50) NOT NULL,
                    miles_required FLOAT NOT NULL,
                    taxes_fees FLOAT DEFAULT 0.0,
                    total_cost FLOAT NOT NULL,
                    availability INTEGER DEFAULT 1,
                    is_partner BOOLEAN DEFAULT FALSE,
                    booking_link VARCHAR(500),
                    fare_basis VARCHAR(50),
                    booking_class VARCHAR(10),
                    stopover_allowed BOOLEAN DEFAULT FALSE,
                    open_jaw_allowed BOOLEAN DEFAULT FALSE,
                    gpu_features JSONB,

                    -- Indexes for GPU acceleration
                    INDEX idx_gpu_awards_departure_arrival (departure_airport, arrival_airport),
                    INDEX idx_gpu_awards_departure_date (departure_date),
                    INDEX idx_gpu_awards_program (program_id),
                    INDEX idx_gpu_awards_cabin_class (cabin_class),
                    INDEX idx_gpu_awards_miles (miles_required),
                    INDEX idx_gpu_awards_airline (airline)
                )
            """)

            # Create materialized view for common queries
            await conn.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS award_search_view AS
                SELECT
                    id, program_id, airline, flight_number,
                    departure_airport, arrival_airport, departure_date, arrival_date,
                    cabin_class, award_type, miles_required, taxes_fees, total_cost,
                    availability, is_partner, booking_link,
                    fare_basis, booking_class, stopover_allowed, open_jaw_allowed,
                    -- Pre-computed features for GPU
                    miles_required AS miles,
                    taxes_fees AS taxes,
                    (arrival_date - departure_date) AS duration_days,
                    CASE WHEN cabin_class = 'economy' THEN 0
                         WHEN cabin_class = 'premium_economy' THEN 1
                         WHEN cabin_class = 'business' THEN 2
                         WHEN cabin_class = 'first' THEN 3
                         ELSE 0 END AS cabin_class_num,
                    (is_partner::int) AS is_partner_int,
                    departure_airport::text::int % 1000 AS dep_airport_hash,
                    arrival_airport::text::int % 1000 AS arr_airport_hash
                FROM awards_gpu
                WITH DATA
            """)

            # Create refresh function for materialized view
            await conn.execute("""
                CREATE OR REPLACE FUNCTION refresh_award_search_view()
                RETURNS TRIGGER AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW award_search_view;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql
            """)

            logger.info("GPU database schema ensured")

    async def insert_awards(self, awards: List[Award]):
        """Bulk insert awards into GPU database"""
        if not self.connected:
            await self.connect()

        if not awards:
            return

        try:
            async with self.pool.acquire() as conn:
                # Prepare data for bulk insert
                data = []
                for award in awards:
                    features = award.to_gpu_features()
                    data.append((
                        award.program_id,
                        award.airline,
                        award.flight_number,
                        award.departure_airport,
                        award.arrival_airport,
                        award.departure_date,
                        award.arrival_date,
                        award.cabin_class,
                        award.award_type,
                        award.miles_required,
                        award.taxes_fees,
                        award.total_cost,
                        award.availability,
                        award.is_partner,
                        award.booking_link,
                        award.fare_basis,
                        award.booking_class,
                        award.stopover_allowed,
                        award.open_jaw_allowed,
                        features
                    ))

                # Use COPY command for maximum performance
                await conn.copy_records_to_table(
                    'awards_gpu',
                    records=data,
                    columns=[
                        'program_id', 'airline', 'flight_number',
                        'departure_airport', 'arrival_airport', 'departure_date', 'arrival_date',
                        'cabin_class', 'award_type', 'miles_required', 'taxes_fees', 'total_cost',
                        'availability', 'is_partner', 'booking_link', 'fare_basis', 'booking_class',
                        'stopover_allowed', 'open_jaw_allowed', 'gpu_features'
                    ]
                )

                # Refresh materialized view
                await conn.execute("SELECT refresh_award_search_view()")

                logger.info(f"Inserted {len(awards)} awards into GPU database")
        except Exception as e:
            logger.error(f"Failed to insert awards: {e}")
            raise

    async def search_awards(self, criteria: Dict[str, Any]) -> List[Dict]:
        """
        Search awards using GPU-accelerated queries.
        criteria can include:
        - departure_airport, arrival_airport
        - departure_date (range or exact)
        - cabin_class
        - miles_range (min, max)
        - max_miles
        - airline
        - is_partner
        - limit
        """
        if not self.connected:
            await self.connect()

        start_time = perf_counter()

        try:
            # Build query dynamically based on criteria
            query = """
                SELECT * FROM award_search_view
                WHERE 1=1
            """

            params = []

            # Departure and arrival airports
            if 'departure_airport' in criteria:
                query += " AND departure_airport = $1"
                params.append(criteria['departure_airport'])
            if 'arrival_airport' in criteria:
                query += " AND arrival_airport = $2"
                params.append(criteria['arrival_airport'])

            # Date range
            if 'departure_date_from' in criteria:
                query += " AND departure_date >= $3"
                params.append(criteria['departure_date_from'])
            if 'departure_date_to' in criteria:
                query += " AND departure_date <= $4"
                params.append(criteria['departure_date_to'])

            # Cabin class
            if 'cabin_class' in criteria:
                query += " AND cabin_class = $5"
                params.append(criteria['cabin_class'])

            # Miles range
            if 'miles_min' in criteria:
                query += " AND miles_required >= $6"
                params.append(criteria['miles_min'])
            if 'miles_max' in criteria:
                query += " AND miles_required <= $7"
                params.append(criteria['miles_max'])

            # Airline
            if 'airline' in criteria:
                query += " AND airline = $8"
                params.append(criteria['airline'])

            # Partner filter
            if 'is_partner' in criteria:
                query += " AND is_partner = $9"
                params.append(criteria['is_partner'])

            # Limit
            if 'limit' in criteria:
                query += " LIMIT $10"
                params.append(criteria['limit'])
            else:
                query += " LIMIT 100"

            # Execute query
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(row))

            elapsed = perf_counter() - start_time
            logger.debug(f"GPU search completed in {elapsed:.4f}s, found {len(results)} results")

            return results
        except Exception as e:
            logger.error(f"GPU search failed: {e}")
            raise

    async def get_award_by_id(self, award_id: int) -> Optional[Dict]:
        """Get a single award by ID"""
        if not self.connected:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM award_search_view WHERE id = $1",
                    award_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get award {award_id}: {e}")
            return None

    async def update_award_features(self, award_id: int, features: Dict):
        """Update GPU features for an award"""
        if not self.connected:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE awards_gpu SET gpu_features = $1 WHERE id = $2",
                    features, award_id
                )
                await conn.execute("SELECT refresh_award_search_view()")
                return True
        except Exception as e:
            logger.error(f"Failed to update award features: {e}")
            return False

# Singleton instance
gpu_db = GPUDBAwardRepository()
