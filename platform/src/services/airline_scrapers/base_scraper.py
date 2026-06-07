"""
Base scraper class for airline award availability.
Designed for high-throughput, low-latency scraping with mechanical sympathy.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, List
from platform.src.models.award_flight import Airline, AwardFlight, FlightClass

logger = logging.getLogger(__name__)

class BaseAirlineScraper(ABC):
    """Abstract base class for airline-specific scrapers."""

    def __init__(self, airline: Airline):
        self.airline = airline
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def initialize(self):
        """Initialize the scraper (async)."""
        import aiohttp
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @abstractmethod
    async def check_award_availability(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        cabin_class: FlightClass = FlightClass.ECONOMY
    ) -> List[AwardFlight]:
        """Check award availability for specific route and dates."""
        pass

    async def _fetch(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Fetch page content with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # Rate limited, exponential backoff
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string into date object."""
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _clean_flight_number(self, flight_number: str) -> str:
        """Clean flight number string."""
        return flight_number.strip().upper()
