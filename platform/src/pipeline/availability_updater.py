"""
Real-time Availability and Pricing Update Pipeline
Distributed system to fetch and update travel availability from multiple sources.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import random
from dataclasses import dataclass
import uuid

from ..intelligence.ar_travel_planner import ar_planner, AwardOpportunity, TravelClass, TravelType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AvailabilityUpdater")

@dataclass
class SourceConfig:
    name: str
    base_url: str
    api_key: str
    update_interval: int
    supported_classes: List[TravelClass]
    supported_types: List[TravelType]

class AvailabilityFetcher:
    """Fetches availability data from external sources"""

    def __init__(self):
        self.sources = [
            SourceConfig(
                name="AwardFlightsAPI",
                base_url="https://api.awardflights.com/v1",
                api_key="district_travel_key_2026",
                update_interval=300,  # 5 minutes
                supported_classes=[TravelClass.ECONOMY, TravelClass.PREMIUM_ECONOMY, TravelClass.BUSINESS],
                supported_types=[TravelType.FLIGHT]
            ),
            SourceConfig(
                name="HotelPointsAPI",
                base_url="https://api.hotelpoints.com/v2",
                api_key="district_hotel_key_2026",
                update_interval=600,  # 10 minutes
                supported_classes=[TravelClass.ECONOMY, TravelClass.PREMIUM_ECONOMY, TravelClass.BUSINESS],
                supported_types=[TravelType.HOTEL]
            ),
            SourceConfig(
                name="CarRentalPointsAPI",
                base_url="https://api.carrentalpoints.com/v1",
                api_key="district_car_key_2026",
                update_interval=900,  # 15 minutes
                supported_classes=[TravelClass.ECONOMY],
                supported_types=[TravelType.CAR_RENTAL]
            )
        ]

        self.session = None
        self.last_updated = {}
        self.error_counts = {source.name: 0 for source in self.sources}
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_successful_update": None
        }

    async def initialize(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("Availability fetcher initialized")

    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("Availability fetcher closed")

    async def fetch_from_source(self, source: SourceConfig) -> Optional[List[Dict]]:
        """Fetch data from a single source"""
        start_time = time.time()
        self.metrics["total_requests"] += 1

        url = f"{source.base_url}/availability"
        headers = {"Authorization": f"Bearer {source.api_key}"}
        params = {
            "limit": 50,
            "include_details": "true"
        }

        try:
            async with self.session.get(url, headers=headers, params=params, timeout=10) as response:
                response_time = time.time() - start_time
                self.metrics["avg_response_time"] = (
                    self.metrics["avg_response_time"] * (self.metrics["total_requests"] - 1) + response_time
                ) / self.metrics["total_requests"]

                if response.status == 200:
                    data = await response.json()
                    self.metrics["successful_requests"] += 1
                    self.metrics["last_successful_update"] = datetime.now().isoformat()
                    self.error_counts[source.name] = 0
                    return data.get("results", [])

                logger.warning(f"Source {source.name} returned status {response.status}")
                self.metrics["failed_requests"] += 1
                self.error_counts[source.name] += 1
                return None

        except Exception as e:
            logger.error(f"Error fetching from {source.name}: {str(e)}")
            self.metrics["failed_requests"] += 1
            self.error_counts[source.name] += 1
            return None

    async def process_opportunity_data(self, data: Dict) -> Optional[AwardOpportunity]:
        """Convert raw data to AwardOpportunity object"""
        try:
            # Map raw data to our format
            travel_class = TravelClass(data.get("cabin_class", "economy").lower())

            if travel_class not in [tc for source in self.sources for tc in source.supported_classes]:
                return None

            travel_type = TravelType(data.get("type", "flight").lower())

            if travel_type not in [tt for source in self.sources for tt in source.supported_types]:
                return None

            # Create opportunity
            opp = AwardOpportunity(
                id=data.get("id", str(uuid.uuid4())),
                title=data.get("title", "Travel Opportunity"),
                description=data.get("description", ""),
                airline=data.get("airline", "Unknown"),
                departure=data.get("departure", "Unknown"),
                arrival=data.get("arrival", "Unknown"),
                departure_date=datetime.fromisoformat(data["departure_date"]),
                return_date=datetime.fromisoformat(data["return_date"]) if data.get("return_date") else None,
                travel_class=travel_class,
                price_in_points=int(data.get("points_required", 0)),
                cash_price=float(data.get("cash_price", 0)),
                availability=int(data.get("availability", 0)),
                duration_days=int(data.get("duration_days", 1)),
                route_distance=float(data.get("distance", 1000)),
                ar_points=[],  # Will be generated by AR planner
                thumbnail_url=data.get("thumbnail_url", ""),
                is_featured=data.get("is_featured", False),
                tags=data.get("tags", [])
            )

            return opp

        except Exception as e:
            logger.error(f"Error processing opportunity data: {str(e)}")
            return None

    async def update_from_source(self, source: SourceConfig):
        """Update opportunities from a single source"""
        logger.info(f"Updating from {source.name}...")
        data = await self.fetch_from_source(source)

        if not data:
            return 0

        processed = 0
        for item in data:
            opp = await self.process_opportunity_data(item)
            if opp:
                # Check if we need to update or add
                existing = ar_planner.get_opportunity_details(opp.id)
                if existing:
                    # Update existing
                    existing.title = opp.title
                    existing.description = opp.description
                    existing.price_in_points = opp.price_in_points
                    existing.cash_price = opp.cash_price
                    existing.availability = opp.availability
                    existing.departure_date = opp.departure_date
                    existing.return_date = opp.return_date
                    existing.ar_points = ar_planner.generate_ar_visualization(existing)
                    existing.value_score = ar_planner.calculate_award_value(existing)
                    logger.info(f"Updated opportunity {opp.id}")
                else:
                    # Add new
                    ar_planner.add_opportunity(opp)
                    logger.info(f"Added new opportunity {opp.id}")

                processed += 1

        logger.info(f"Processed {processed} opportunities from {source.name}")
        return processed

    async def run_update_cycle(self):
        """Run a complete update cycle across all sources"""
        logger.info("Starting availability update cycle...")

        total_processed = 0
        for source in self.sources:
            try:
                processed = await self.update_from_source(source)
                total_processed += processed
                self.last_updated[source.name] = datetime.now()
            except Exception as e:
                logger.error(f"Error updating from {source.name}: {str(e)}")

        logger.info(f"Update cycle complete. Processed {total_processed} opportunities.")
        return total_processed

class RealTimePriceUpdater:
    """Handles real-time price updates and pushes to AR planner"""

    def __init__(self):
        self.price_updates = asyncio.Queue()
        self.active = False

    async def start(self):
        """Start the real-time price update service"""
        self.active = True
        logger.info("Real-time price updater started")
        await self._process_updates()

    async def _process_updates(self):
        """Process price updates from various sources"""
        while self.active:
            try:
                update = await self.price_updates.get()
                await ar_planner.price_updates.put(update)
                logger.debug(f"Processed price update: {update}")
            except Exception as e:
                logger.error(f"Error processing price update: {str(e)}")

    async def stop(self):
        """Stop the service"""
        self.active = False
        logger.info("Real-time price updater stopped")

class PipelineOrchestrator:
    """Orchestrates the entire availability update pipeline"""

    def __init__(self):
        self.fetcher = AvailabilityFetcher()
        self.price_updater = RealTimePriceUpdater()
        self.running = False
        self.metrics = {
            "last_full_update": None,
            "avg_update_interval": 0,
            "total_updates": 0
        }

    async def initialize(self):
        """Initialize the pipeline"""
        await self.fetcher.initialize()
        await self.price_updater.start()
        logger.info("Pipeline orchestrator initialized")

    async def run(self):
        """Run the continuous update pipeline"""
        self.running = True
        logger.info("Starting availability pipeline...")

        # Initial full update
        await self._perform_full_update()

        # Continuous updates
        while self.running:
            try:
                # Wait for next scheduled update
                next_update = datetime.now() + timedelta(seconds=300)  # Default 5 min
                sleep_time = 300

                # Check each source's interval
                for source in self.fetcher.sources:
                    time_since_update = (datetime.now() - self.fetcher.last_updated.get(source.name, datetime.min)).total_seconds()
                    source_interval = source.update_interval

                    if time_since_update > source_interval:
                        sleep_time = min(sleep_time, source_interval)
                        next_update = datetime.now() + timedelta(seconds=source_interval)

                # Sleep until next update
                await asyncio.sleep(sleep_time)

                # Perform update
                processed = await self._perform_full_update()
                self.metrics["total_updates"] += 1
                self.metrics["last_full_update"] = datetime.now().isoformat()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in pipeline: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _perform_full_update(self) -> int:
        """Perform a full update cycle"""
        logger.info("Performing full availability update...")
        start_time = datetime.now()

        processed = await self.fetcher.run_update_cycle()

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Full update completed in {duration:.2f}s. Processed {processed} opportunities.")

        return processed

    async def shutdown(self):
        """Clean shutdown of the pipeline"""
        self.running = False
        await self.price_updater.stop()
        await self.fetcher.close()
        logger.info("Pipeline orchestrator shutdown complete")

# Global pipeline instance
pipeline = PipelineOrchestrator()

async def start_pipeline():
    """Start the availability update pipeline"""
    await pipeline.initialize()
    await pipeline.run()

async def shutdown_pipeline():
    """Shutdown the availability update pipeline"""
    await pipeline.shutdown()

if __name__ == "__main__":
    # For testing
    asyncio.run(start_pipeline())
