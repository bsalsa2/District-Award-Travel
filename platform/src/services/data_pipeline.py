import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from bs4 import BeautifulSoup
import json
from config.settings import settings
import redis
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models.base import Base, PredictionCache
from services.ai_inference import AwardPredictor

logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self):
        self.redis = redis.Redis.from_url(settings.REDIS_URL)
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.Session = sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        self.predictor = AwardPredictor()
        self.session = aiohttp.ClientSession()

    async def fetch_airline_data(self, airline: str, date: datetime) -> Dict[str, Any]:
        """Fetch real-time data from airline APIs"""
        endpoints = {
            "AA": "https://api.aa.com/v1/schedules",
            "DL": "https://api.delta.com/v1/availability",
            "UA": "https://api.united.com/v1/loadfactors"
        }

        if airline not in endpoints:
            return {}

        params = {
            "origin": "JFK",
            "destination": "LAX",
            "departure_date": date.strftime("%Y-%m-%d"),
            "limit": 100
        }

        try:
            async with self.session.get(
                endpoints[airline],
                params=params,
                headers={"Authorization": f"Bearer {self._get_api_key(airline)}"}
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"Failed to fetch data from {airline}: {e}")

        return {}

    async def scrape_external_data(self) -> Dict[str, Any]:
        """Scrape external data sources for events affecting travel"""
        sources = {
            "holidays": "https://www.timeanddate.com/holidays/us/",
            "weather": "https://weather.com/flight-delays",
            "geopolitical": "https://apnews.com/hub/geopolitical-tensions"
        }

        results = {}

        for source, url in sources.items():
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        # Extract relevant data based on source
                        if source == "holidays":
                            results["holidays"] = self._parse_holidays(soup)
                        elif source == "weather":
                            results["weather_alerts"] = self._parse_weather(soup)
                        elif source == "geopolitical":
                            results["geopolitical_events"] = self._parse_geopolitical(soup)
            except Exception as e:
                logger.error(f"Failed to scrape {source}: {e}")

        return results

    def _parse_holidays(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse holiday data from HTML"""
        holidays = []
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    holidays.append({
                        "date": cols[0].text.strip(),
                        "name": cols[1].text.strip(),
                        "type": cols[2].text.strip()
                    })
        return holidays

    def _parse_weather(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse weather alerts"""
        alerts = []
        # Simplified parsing - actual implementation would extract flight delay data
        return [{"severity": "moderate", "regions": ["Northeast", "Midwest"]}]

    def _parse_geopolitical(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse geopolitical events"""
        events = []
        # Simplified parsing
        return [{"region": "Europe", "risk_level": "high"}]

    async def process_airline_data(self, airline_data: Dict[str, Any]) -> None:
        """Process and store airline data for model training"""
        # This would be where we extract features for the AI model
        features = {
            "airline": airline_data.get("carrier", ""),
            "route": f"{airline_data.get('origin', '')}_{airline_data.get('destination', '')}",
            "date": airline_data.get("date", ""),
            "load_factor": airline_data.get("load_factor", 0),
            "capacity": airline_data.get("capacity", 0),
            "bookings": airline_data.get("bookings", 0),
            "cancellations": airline_data.get("cancellations", 0),
            "processed_at": datetime.utcnow().isoformat()
        }

        # Store in Redis for real-time access
        route_key = f"airline:{features['route']}:{features['date']}"
        self.redis.hset(route_key, mapping=features)
        self.redis.expire(route_key, 86400)  # 24 hours

    async def update_predictions(self) -> None:
        """Update predictions for all monitored routes"""
        logger.info("Starting prediction update cycle")

        # Get all monitored routes from cache
        route_keys = self.redis.smembers("monitored_routes")
        if not route_keys:
            logger.warning("No routes to monitor")
            return

        predictions = []
        for route_key in route_keys:
            route_key = route_key.decode('utf-8')
            # Generate predictions for next 30 days
            for days_ahead in range(1, 31):
                departure_date = datetime.now() + timedelta(days=days_ahead)
                prediction = self.predictor.predict(
                    route_key,
                    departure_date,
                    passengers=1
                )
                predictions.append({
                    "route_key": route_key,
                    "departure_date": departure_date.strftime("%Y-%m-%d"),
                    "prediction": prediction
                })

        # Store predictions in database
        await self._store_predictions(predictions)

        logger.info(f"Updated {len(predictions)} predictions")

    async def _store_predictions(self, predictions: List[Dict]) -> None:
        """Store predictions in database with async session"""
        async with self.Session() as session:
            for pred in predictions:
                db_pred = PredictionCache(
                    route_key=pred["route_key"],
                    departure_date=datetime.strptime(pred["departure_date"], "%Y-%m-%d").date(),
                    prediction=json.dumps(pred["prediction"]),
                    confidence=pred["prediction"]["confidence"],
                    expires_at=datetime.utcnow() + timedelta(seconds=settings.PREDICTION_CACHE_TTL)
                )
                session.add(db_pred)
            await session.commit()

    async def run(self):
        """Main pipeline runner"""
        logger.info("Starting data pipeline")

        while True:
            try:
                # Update predictions every 15 minutes
                await self.update_predictions()

                # Scrape external data every hour
                external_data = await self.scrape_external_data()
                self.redis.set("external_data", json.dumps(external_data))
                self.redis.expire("external_data", 3600)

                # Fetch airline data for top routes
                await self._fetch_top_routes_data()

                # Sleep until next cycle
                await asyncio.sleep(settings.SCRAPE_INTERVAL)

            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _fetch_top_routes_data(self):
        """Fetch data for top routes based on historical demand"""
        top_routes = [
            "JFK_LAX_economy",
            "LAX_JFK_business",
            "SFO_NRT_premium_economy",
            "LHR_JFK_first"
        ]

        for route in top_routes:
            # Fetch data for next 7 days
            for days_ahead in range(1, 8):
                departure_date = datetime.now() + timedelta(days=days_ahead)
                airline_data = await self.fetch_airline_data("AA", departure_date)
                if airline_data:
                    await self.process_airline_data(airline_data)

    def _get_api_key(self, airline: str) -> str:
        """Get API key for airline (simplified)"""
        keys = {
            "AA": "aa_api_key_123",
            "DL": "dl_api_key_456",
            "UA": "ua_api_key_789"
        }
        return keys.get(airline, "")
