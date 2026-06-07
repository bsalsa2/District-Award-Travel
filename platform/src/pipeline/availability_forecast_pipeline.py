"""
Distributed pipeline for award flight availability forecasting
Handles data collection, model training, and prediction serving
"""

import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
from platform.src.intelligence.availability_forecast import get_forecaster
from pathlib import Path
import json
import sqlite3
from dataclasses import asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('platform/logs/forecast_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AvailabilityForecastPipeline:
    """
    End-to-end pipeline for award flight availability forecasting
    """

    def __init__(self):
        self.forecaster = get_forecaster()
        self.db_path = 'platform/data/award_flights.db'
        self.cache_dir = Path('platform/cache/forecast')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("AvailabilityForecastPipeline initialized")

    async def fetch_award_availability_data(self) -> List[Dict]:
        """
        Fetch award availability data from external sources
        (Simulated - would integrate with airline APIs in production)
        """
        try:
            # Simulate API calls to multiple sources
            sources = [
                {'name': 'AA_API', 'url': 'https://api.aa.com/awards'},
                {'name': 'DL_API', 'url': 'https://api.delta.com/awards'},
                {'name': 'UA_API', 'url': 'https://api.united.com/awards'},
                {'name': 'BA_API', 'url': 'https://api.britishairways.com/awards'}
            ]

            results = []
            async with aiohttp.ClientSession() as session:
                tasks = []
                for source in sources:
                    tasks.append(self._fetch_source(session, source))

                responses = await asyncio.gather(*tasks, return_exceptions=True)

                for response in responses:
                    if isinstance(response, Exception):
                        logger.error(f"Error fetching from source: {response}")
                    elif response:
                        results.extend(response)

            logger.info(f"Fetched {len(results)} award availability records")
            return results

        except Exception as e:
            logger.error(f"Error in fetch_award_availability_data: {e}")
            return []

    async def _fetch_source(self, session: aiohttp.ClientSession, source: Dict) -> List[Dict]:
        """
        Fetch data from a single source
        """
        try:
            # Simulate API delay
            await asyncio.sleep(0.1)

            # Simulate response
            mock_data = [
                {
                    'flight_date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                    'departure_airport': 'JFK',
                    'arrival_airport': 'LAX',
                    'route_key': 'JFK-LAX',
                    'availability_score': 0.8 - (i * 0.01),
                    'seats_available': 5 + (i % 3),
                    'booking_class': 'Award',
                    'airline': source['name'].split('_')[0],
                    'distance': 2475,
                    'created_at': datetime.now().isoformat()
                }
                for i in range(30)
            ]

            return mock_data

        except Exception as e:
            logger.error(f"Error fetching from {source['name']}: {e}")
            return []

    def store_award_data(self, data: List[Dict]) -> bool:
        """
        Store award availability data in database
        """
        try:
            if not data:
                logger.warning("No data to store")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_flight_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_date TEXT NOT NULL,
                departure_airport TEXT NOT NULL,
                arrival_airport TEXT NOT NULL,
                route_key TEXT NOT NULL,
                availability_score REAL NOT NULL,
                seats_available INTEGER NOT NULL,
                booking_class TEXT NOT NULL,
                airline TEXT NOT NULL,
                distance INTEGER NOT NULL,
                day_of_week INTEGER,
                week_of_year INTEGER,
                month INTEGER,
                is_holiday INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Insert data
            for record in data:
                cursor.execute("""
                INSERT INTO award_flight_availability
                (flight_date, departure_airport, arrival_airport, route_key,
                 availability_score, seats_available, booking_class, airline,
                 distance, day_of_week, week_of_year, month, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['flight_date'],
                    record['departure_airport'],
                    record['arrival_airport'],
                    record['route_key'],
                    record['availability_score'],
                    record['seats_available'],
                    record['booking_class'],
                    record['airline'],
                    record['distance'],
                    record.get('day_of_week'),
                    record.get('week_of_year'),
                    record.get('month'),
                    record['created_at']
                ))

            conn.commit()
            conn.close()

            logger.info(f"Stored {len(data)} records in database")
            return True

        except Exception as e:
            logger.error(f"Error storing award data: {e}")
            conn.close()
            return False

    async def run_training_pipeline(self):
        """
        Run the complete training pipeline
        """
        logger.info("Starting training pipeline...")

        try:
            # Step 1: Fetch data
            logger.info("Step 1/4: Fetching award availability data...")
            data = await self.fetch_award_availability_data()

            if not data:
                logger.warning("No data fetched, skipping training")
                return False

            # Step 2: Store data
            logger.info("Step 2/4: Storing data in database...")
            if not self.store_award_data(data):
                logger.warning("Failed to store data")
                return False

            # Step 3: Train model
            logger.info("Step 3/4: Training forecast model...")
            if not self.forecaster.train():
                logger.error("Model training failed")
                return False

            # Step 4: Cache predictions for popular routes
            logger.info("Step 4/4: Caching predictions...")
            self._cache_popular_routes()

            logger.info("Training pipeline completed successfully")
            return True

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            return False

    def _cache_popular_routes(self):
        """
        Cache predictions for popular routes to improve response time
        """
        try:
            # Popular routes
            popular_routes = [
                'JFK-LAX', 'JFK-SFO', 'JFK-MIA', 'JFK-LHR',
                'LAX-JFK', 'SFO-JFK', 'MIA-JFK', 'LHR-JFK'
            ]

            # Next 7 days
            dates = [
                (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                for i in range(7)
            ]

            # Get predictions
            predictions = self.forecaster.forecast_multiple(popular_routes, dates)

            # Cache to JSON
            cache_data = [asdict(p) for p in predictions]
            cache_path = self.cache_dir / 'popular_routes.json'

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached predictions for {len(predictions)} route-date combinations")

        except Exception as e:
            logger.error(f"Error caching predictions: {e}")

    def get_cached_predictions(self) -> List[Dict]:
        """
        Get cached predictions for popular routes
        """
        try:
            cache_path = self.cache_dir / 'popular_routes.json'
            if not cache_path.exists():
                return []

            with open(cache_path, 'r') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error reading cached predictions: {e}")
            return []

    async def run_forecast_job(self):
        """
        Run the forecast job (training + serving)
        """
        # Run training pipeline
        training_success = await self.run_training_pipeline()

        if not training_success:
            logger.warning("Training failed, using cached model")

        # Return performance metrics
        return self.forecaster.get_model_performance()

# Singleton instance
pipeline = AvailabilityForecastPipeline()

def get_pipeline() -> AvailabilityForecastPipeline:
    """Get the global pipeline instance"""
    return pipeline
