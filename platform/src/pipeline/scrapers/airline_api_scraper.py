import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from ..adapters.airline_client import (
    AirlineRequest,
    AirlineResponse,
    AirlineClientFactory,
    CircuitBreaker,
    CacheManager,
    with_retry
)

logger = logging.getLogger(__name__)

@dataclass
class FlightOffer:
    airline: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin: str
    destination: str
    cabin_class: str
    price: float
    currency: str
    offer_id: str
    booking_url: str
    duration: int  # in minutes
    stops: int
    fare_basis: str
    included_bags: int
    timestamp: datetime = datetime.utcnow()

class AirlineAPIScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            max_failures=config.get("circuit_breaker_max_failures", 5),
            reset_timeout=config.get("circuit_breaker_reset_timeout", 60)
        )
        self.cache_manager = CacheManager(cache_dir=config.get("cache_dir", "/tmp/airline_cache"))

        # Initialize clients
        self.clients = {}
        for airline in config.get("airlines", ["united", "delta", "american"]):
            api_key = config["api_keys"][airline]
            self.clients[airline] = AirlineClientFactory.create_client(
                airline=airline,
                api_key=api_key,
                circuit_breaker=self.circuit_breaker,
                cache_manager=self.cache_manager
            )

    async def close(self):
        """Clean up resources"""
        for client in self.clients.values():
            await client.close()

    @with_retry(max_attempts=3, base_delay=1.0)
    async def get_flight_offers(
        self,
        origin: str,
        destination: str,
        departure_date: datetime,
        return_date: Optional[datetime] = None,
        cabin_class: str = "economy",
        adults: int = 1,
        max_stops: int = 1
    ) -> List[FlightOffer]:
        """
        Get flight offers from multiple airlines
        Returns list of FlightOffer objects
        """
        offers = []

        # Create requests for each airline
        requests = []
        for airline in self.clients.keys():
            params = {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date.strftime("%Y-%m-%d"),
                "adults": adults,
                "cabin_class": cabin_class,
                "max_stops": max_stops,
                "limit": 20
            }

            if return_date:
                params["return_date"] = return_date.strftime("%Y-%m-%d")

            request = AirlineRequest(
                airline_code=airline,
                endpoint="flights/search",
                params=params,
                method="GET"
            )
            requests.append((airline, request))

        # Execute requests concurrently
        tasks = []
        for airline, request in requests:
            task = asyncio.create_task(
                self._process_airline_request(airline, request)
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for airline, result in zip(self.clients.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get offers from {airline}: {str(result)}")
                continue

            if result:
                offers.extend(result)

        # Deduplicate offers by offer_id
        unique_offers = {offer.offer_id: offer for offer in offers}
        return list(unique_offers.values())

    async def _process_airline_request(
        self,
        airline: str,
        request: AirlineRequest
    ) -> Optional[List[FlightOffer]]:
        """Process a single airline request and convert to FlightOffer objects"""
        try:
            response = await self.clients[airline]._make_request(request)

            if not self.clients[airline].validate_response(response):
                logger.warning(f"Invalid response from {airline}: {response.status_code}")
                return None

            if response.status_code != 200:
                logger.warning(f"Non-200 response from {airline}: {response.status_code}")
                return None

            # Convert API response to FlightOffer objects
            return self._parse_flight_offers(airline, response)

        except Exception as e:
            logger.error(f"Error processing {airline} request: {str(e)}")
            return None

    def _parse_flight_offers(
        self,
        airline: str,
        response: AirlineResponse
    ) -> List[FlightOffer]:
        """Parse airline-specific response into standardized FlightOffer objects"""
        offers = []

        data = response.data

        # Handle different airline response formats
        if airline == "united":
            flight_data = data.get("flights", [])
            for flight in flight_data:
                try:
                    offer = FlightOffer(
                        airline="United",
                        flight_number=flight.get("flight_number", ""),
                        departure_time=datetime.fromisoformat(flight["departure_time"]),
                        arrival_time=datetime.fromisoformat(flight["arrival_time"]),
                        origin=flight["origin"],
                        destination=flight["destination"],
                        cabin_class=flight.get("cabin_class", "economy"),
                        price=float(flight["price"]["amount"]),
                        currency=flight["price"]["currency"],
                        offer_id=flight.get("offer_id", ""),
                        booking_url=flight.get("booking_url", ""),
                        duration=flight.get("duration_minutes", 0),
                        stops=flight.get("stops", 0),
                        fare_basis=flight.get("fare_basis", ""),
                        included_bags=flight.get("included_bags", 0)
                    )
                    offers.append(offer)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse United flight: {str(e)}")
                    continue

        elif airline == "delta":
            itineraries = data.get("itineraries", [])
            for itinerary in itineraries:
                try:
                    segments = itinerary.get("segments", [])
                    if not segments:
                        continue

                    first_segment = segments[0]
                    last_segment = segments[-1]

                    offer = FlightOffer(
                        airline="Delta",
                        flight_number=first_segment.get("flight_number", ""),
                        departure_time=datetime.fromisoformat(first_segment["departure_time"]),
                        arrival_time=datetime.fromisoformat(last_segment["arrival_time"]),
                        origin=first_segment["origin"],
                        destination=last_segment["destination"],
                        cabin_class=itinerary.get("cabin_class", "economy"),
                        price=float(itinerary["price"]["amount"]),
                        currency=itinerary["price"]["currency"],
                        offer_id=itinerary.get("offer_id", ""),
                        booking_url=itinerary.get("booking_url", ""),
                        duration=itinerary.get("duration_minutes", 0),
                        stops=len(segments) - 1,
                        fare_basis=itinerary.get("fare_basis", ""),
                        included_bags=itinerary.get("included_bags", 0)
                    )
                    offers.append(offer)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse Delta itinerary: {str(e)}")
                    continue

        elif airline == "american":
            offers_data = data.get("offers", [])
            for offer_data in offers_data:
                try:
                    segments = offer_data.get("segments", [])
                    if not segments:
                        continue

                    first_segment = segments[0]
                    last_segment = segments[-1]

                    offer = FlightOffer(
                        airline="American",
                        flight_number=first_segment.get("flight_number", ""),
                        departure_time=datetime.fromisoformat(first_segment["departure_time"]),
                        arrival_time=datetime.fromisoformat(last_segment["arrival_time"]),
                        origin=first_segment["origin"],
                        destination=last_segment["destination"],
                        cabin_class=offer_data.get("cabin_class", "economy"),
                        price=float(offer_data["price"]["amount"]),
                        currency=offer_data["price"]["currency"],
                        offer_id=offer_data.get("offer_id", ""),
                        booking_url=offer_data.get("booking_url", ""),
                        duration=offer_data.get("duration_minutes", 0),
                        stops=len(segments) - 1,
                        fare_basis=offer_data.get("fare_basis", ""),
                        included_bags=offer_data.get("included_bags", 0)
                    )
                    offers.append(offer)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse American offer: {str(e)}")
                    continue

        return offers

    async def get_flight_status(
        self,
        airline: str,
        flight_number: str,
        departure_date: datetime,
        origin: str,
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """Get current status of a specific flight"""
        client = self.clients.get(airline.lower())
        if not client:
            raise ValueError(f"Unsupported airline: {airline}")

        request = AirlineRequest(
            airline_code=airline.lower(),
            endpoint=f"flights/status/{flight_number}",
            params={
                "departure_date": departure_date.strftime("%Y-%m-%d"),
                "origin": origin,
                "destination": destination
            },
            method="GET"
        )

        try:
            response = await client._make_request(request)
            if response.status_code == 200 and client.validate_response(response):
                return response.data
            return None
        except Exception as e:
            logger.error(f"Failed to get flight status: {str(e)}")
            return None

    async def get_airport_info(self, airport_code: str) -> Optional[Dict[str, Any]]:
        """Get information about an airport"""
        # This would be implemented per airline API
        # For now, return mock data
        return {
            "code": airport_code,
            "name": f"Airport {airport_code}",
            "city": "Unknown",
            "country": "US",
            "timezone": "UTC"
        }
