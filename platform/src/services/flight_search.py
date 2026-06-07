"""
High-performance flight search service.
Coordinates multiple airline scrapers with caching and rate limiting.
"""

import asyncio
import logging
from datetime import date
from typing import List, Optional
from platform.src.models.award_flight import Airline, AwardFlight, AwardSearchRequest, FlightClass
from platform.src.services.airline_scrapers.american_scraper import AmericanAirlinesScraper
from platform.src.services.airline_scrapers.delta_scraper import DeltaAirlinesScraper
from platform.src.services.flight_cache import FlightCache
from platform.src.services.airline_scrapers.base_scraper import BaseAirlineScraper

logger = logging.getLogger(__name__)

class FlightSearchService:
    """Service for searching award flight availability across multiple airlines."""

    def __init__(self, cache: FlightCache):
        self.cache = cache
        self.scrapers = {
            Airline.AA: AmericanAirlinesScraper(),
            Airline.DL: DeltaAirlinesScraper(),
            # Add more scrapers as needed
        }
        self.rate_limits = {
            Airline.AA: 5,  # requests per second
            Airline.DL: 5,
        }
        self.last_request_times = {}

    async def initialize(self):
        """Initialize all scrapers."""
        await asyncio.gather(*[scraper.initialize() for scraper in self.scrapers.values()])

    async def close(self):
        """Clean up all scrapers."""
        await asyncio.gather(*[scraper.close() for scraper in self.scrapers.values()])

    async def _check_rate_limit(self, airline: Airline) -> bool:
        """Check if we're within rate limits for an airline."""
        now = asyncio.get_event_loop().time()
        last_time = self.last_request_times.get(airline, 0)
        min_interval = 1.0 / self.rate_limits.get(airline, 5)

        if now - last_time < min_interval:
            await asyncio.sleep(min_interval - (now - last_time))
            self.last_request_times[airline] = asyncio.get_event_loop().time()
            return True

        self.last_request_times[airline] = now
        return True

    async def _search_airline(
        self,
        airline: Airline,
        request: AwardSearchRequest
    ) -> List[AwardFlight]:
        """Search a single airline for award availability."""
        if airline not in self.scrapers:
            return []

        await self._check_rate_limit(airline)

        try:
            scraper = self.scrapers[airline]
            flights = await scraper.check_award_availability(
                origin=request.origin,
                destination=request.destination,
                departure_date=request.departure_date,
                return_date=request.return_date,
                cabin_class=request.cabin_class
            )

            # Filter by airline if specified
            if request.airlines and airline not in request.airlines:
                flights = []

            # Filter by max miles
            if request.max_miles:
                flights = [f for f in flights if f.award_miles <= request.max_miles]

            return flights

        except Exception as e:
            logger.error(f"Error searching {airline} awards: {e}")
            return []

    async def search_award_flights(
        self,
        request: AwardSearchRequest
    ) -> List[AwardFlight]:
        """Search for award flights across all supported airlines."""
        # Check cache first
        cached_flights = await self.cache.get_flights(request)
        if cached_flights is not None:
            logger.info(f"Cache hit for {request.origin}-{request.destination}")
            return cached_flights

        logger.info(f"Cache miss for {request.origin}-{request.destination}, searching...")

        # Search all airlines in parallel
        tasks = []
        for airline in Airline:
            if request.airlines and airline not in request.airlines:
                continue
            tasks.append(self._search_airline(airline, request))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine and sort results
        flights = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in search: {result}")
                continue
            flights.extend(result)

        # Sort by award miles (cheapest first)
        flights.sort(key=lambda f: f.award_miles)

        # Apply limit
        flights = flights[:request.limit]

        # Cache results
        if flights:
            await self.cache.set_flights(request, flights)

        return flights

    async def search_multiple_dates(
        self,
        request: AwardSearchRequest,
        date_range: int = 7
    ) -> Dict[date, List[AwardFlight]]:
        """Search for award flights across a date range."""
        results = {}

        for day_offset in range(date_range):
            search_date = request.departure_date + timedelta(days=day_offset)
            modified_request = request.copy(update={"departure_date": search_date})

            flights = await self.search_award_flights(modified_request)
            if flights:
                results[search_date] = flights

        return results
