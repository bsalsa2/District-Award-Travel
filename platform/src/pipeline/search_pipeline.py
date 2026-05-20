import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sqlite3
from pathlib import Path

from .scrapers.united import UnitedScraper
from .scrapers.delta import DeltaScraper
from .scrapers.american import AmericanScraper
from .aggregator import AwardAggregator
from .scheduler import SearchScheduler

# Configure logging for high-throughput systems
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('award_search_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

class AwardSearchPipeline:
    """
    High-performance award search pipeline with mechanical sympathy principles.
    Designed for maximum throughput with minimal latency.
    """

    def __init__(self, db_path: str = "award_search.db"):
        self.db_path = db_path
        self._initialize_database()

        # Initialize scrapers with connection pooling
        self.scrapers = [
            UnitedScraper(),
            DeltaScraper(),
            AmericanScraper()
        ]

        # Initialize aggregator with SQLite cache
        self.aggregator = AwardAggregator(db_path)

        # Initialize scheduler
        self.scheduler = SearchScheduler(self)

    def _initialize_database(self) -> None:
        """Initialize SQLite database with optimal schema for award data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables with optimal indexing for fast queries
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS award_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            date TEXT NOT NULL,
            airline TEXT NOT NULL,
            flight_number TEXT NOT NULL,
            cabin TEXT NOT NULL,
            miles_required INTEGER NOT NULL,
            taxes_usd REAL NOT NULL,
            available_seats INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(origin, destination, date, airline, flight_number)
        )
        """)

        # Create indexes for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_origin_destination_date ON award_searches(origin, destination, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_miles_required ON award_searches(miles_required)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON award_searches(date)")

        conn.commit()
        conn.close()

    async def search_route(
        self,
        origin: str,
        destination: str,
        date: str,
        max_workers: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for award availability across multiple airlines concurrently.

        Args:
            origin: Origin airport code (e.g., 'JFK')
            destination: Destination airport code (e.g., 'LAX')
            date: Date in YYYY-MM-DD format
            max_workers: Number of concurrent workers

        Returns:
            List of award availability results sorted by value
        """
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

        # Create semaphore for controlled concurrency
        semaphore = asyncio.Semaphore(max_workers)

        async def worker(scraper):
            async with semaphore:
                try:
                    results = await scraper.search(origin, destination, date)
                    return results
                except Exception as e:
                    logger.error(f"Error in {scraper.__class__.__name__}: {str(e)}")
                    return []

        # Run all scrapers concurrently
        tasks = [worker(scraper) for scraper in self.scrapers]
        results = await asyncio.gather(*tasks)

        # Flatten results and deduplicate
        all_results = []
        for result_list in results:
            all_results.extend(result_list)

        # Aggregate and cache results
        aggregated = self.aggregator.aggregate_and_cache(all_results, origin, destination, date)

        logger.info(f"Found {len(aggregated)} award options for {origin}->{destination} on {date}")
        return aggregated

    async def run_hourly_searches(self) -> None:
        """Run scheduled searches for all active client routes."""
        await self.scheduler.run_hourly_searches()

    def get_cached_results(
        self,
        origin: str,
        destination: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve cached results from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        SELECT
            airline,
            flight_number,
            origin,
            destination,
            date,
            cabin,
            miles_required,
            taxes_usd,
            available_seats
        FROM award_searches
        WHERE origin = ? AND destination = ? AND date = ?
        ORDER BY miles_required ASC
        """, (origin, destination, date))

        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results

    def close(self) -> None:
        """Clean up resources."""
        for scraper in self.scrapers:
            if hasattr(scraper, 'close'):
                scraper.close()
        self.scheduler.close()

async def main():
    """Example usage of the award search pipeline."""
    pipeline = AwardSearchPipeline()

    # Example search
    results = await pipeline.search_route("JFK", "LAX", "2026-06-15")
    print(f"Found {len(results)} award options")

    # Example cached retrieval
    cached = pipeline.get_cached_results("JFK", "LAX", "2026-06-15")
    print(f"Cached results: {len(cached)}")

    # Start scheduler (in a real app, this would run in background)
    # await pipeline.run_hourly_searches()

    pipeline.close()

if __name__ == "__main__":
    asyncio.run(main())
