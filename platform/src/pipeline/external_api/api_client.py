"""
External Travel API Client Layer
Handles communication with third-party travel APIs (flights, hotels, car rentals)
Implements retry logic, rate limiting, and circuit breaking
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Any, Optional, List
import time
from functools import wraps
import hashlib
from platform.src.pipeline.cache.redis_cache import RedisCache
from platform.src.pipeline.external_api.exceptions import (
    APIRateLimitExceeded,
    APITimeoutError,
    APIAuthError,
    APIDataError
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class APIClient:
    """Base class for all external API clients"""

    def __init__(self, api_name: str, base_url: str, api_key: str, timeout: int = 30):
        self.api_name = api_name
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.session = None
        self.cache = RedisCache()
        self.rate_limit = 100  # requests per minute
        self.last_request_time = 0
        self.request_count = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _check_rate_limit(self):
        """Check if we're within rate limits"""
        now = time.time()
        if now - self.last_request_time > 60:
            self.request_count = 0
            self.last_request_time = now
        elif self.request_count >= self.rate_limit:
            raise APIRateLimitExceeded(
                f"Rate limit exceeded for {self.api_name}. Max {self.rate_limit} requests per minute."
            )
        self.request_count += 1

    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate a unique cache key for the request"""
        key_str = f"{endpoint}:{json.dumps(params, sort_keys=True)}:{self.api_key}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Make an API request with caching and retry logic"""
        cache_key = self._generate_cache_key(endpoint, params or {})

        # Try to get from cache first
        if use_cache:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {self.api_name}/{endpoint}")
                return json.loads(cached_data)

        # Check rate limits
        self._check_rate_limit()

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 429:
                        raise APIRateLimitExceeded(f"API rate limit hit for {self.api_name}")
                    elif response.status == 401:
                        raise APIAuthError(f"Authentication failed for {self.api_name}")
                    elif response.status == 408:
                        raise APITimeoutError(f"Request timeout for {self.api_name}")
                    elif response.status >= 500:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        raise APITimeoutError(f"Server error for {self.api_name}")

                    response_data = await response.json()

                    # Validate response data
                    if not response_data or "error" in response_data:
                        raise APIDataError(f"Invalid data from {self.api_name}: {response_data}")

                    # Cache the response
                    if use_cache:
                        cache_ttl = 300  # 5 minutes for most data
                        if "cache_ttl" in response_data:
                            cache_ttl = response_data["cache_ttl"]
                        self.cache.set(cache_key, json.dumps(response_data), ttl=cache_ttl)

                    return response_data

            except aiohttp.ClientError as e:
                if attempt == max_retries - 1:
                    raise APITimeoutError(f"Network error for {self.api_name}: {str(e)}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        raise APITimeoutError(f"Failed to get response from {self.api_name} after {max_retries} attempts")

class FlightAPIClient(APIClient):
    """Client for flight booking APIs"""

    def __init__(self, api_key: str):
        super().__init__(
            api_name="flight_booking",
            base_url="https://api.flightdata.com/v1",
            api_key=api_key
        )

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        cabin_class: str = "economy",
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "USD",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for flights between two airports"""
        params = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "cabin_class": cabin_class,
            "adults": adults,
            "children": children,
            "infants": infants,
            "currency": currency,
            "limit": limit
        }

        response = await self._make_request("GET", "flights/search", params=params)
        return response.get("flights", [])

    async def get_flight_details(self, flight_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific flight"""
        response = await self._make_request("GET", f"flights/{flight_id}")
        return response.get("flight", {})

    async def check_availability(self, flight_id: str, seats: int = 1) -> bool:
        """Check if seats are available on a flight"""
        params = {"seats": seats}
        response = await self._make_request("GET", f"flights/{flight_id}/availability", params=params)
        return response.get("available", False)

class HotelAPIClient(APIClient):
    """Client for hotel booking APIs"""

    def __init__(self, api_key: str):
        super().__init__(
            api_name="hotel_booking",
            base_url="https://api.hoteldata.com/v1",
            api_key=api_key
        )

    async def search_hotels(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int = 1,
        rooms: int = 1,
        currency: str = "USD",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for hotels in a location"""
        params = {
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "rooms": rooms,
            "currency": currency,
            "limit": limit
        }

        response = await self._make_request("GET", "hotels/search", params=params)
        return response.get("hotels", [])

    async def get_hotel_details(self, hotel_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific hotel"""
        response = await self._make_request("GET", f"hotels/{hotel_id}")
        return response.get("hotel", {})

    async def check_room_availability(
        self,
        hotel_id: str,
        room_type_id: str,
        check_in: str,
        check_out: str
    ) -> Dict[str, Any]:
        """Check room availability for specific dates"""
        params = {
            "check_in": check_in,
            "check_out": check_out
        }
        response = await self._make_request(
            "GET",
            f"hotels/{hotel_id}/rooms/{room_type_id}/availability",
            params=params
        )
        return response.get("availability", {})

class CarRentalAPIClient(APIClient):
    """Client for car rental APIs"""

    def __init__(self, api_key: str):
        super().__init__(
            api_name="car_rental",
            base_url="https://api.carrental.com/v1",
            api_key=api_key
        )

    async def search_vehicles(
        self,
        location: str,
        from_time: str,
        to_time: str,
        vehicle_class: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for available rental vehicles"""
        params = {
            "location": location,
            "from_time": from_time,
            "to_time": to_time,
            "limit": limit
        }
        if vehicle_class:
            params["vehicle_class"] = vehicle_class

        response = await self._make_request("GET", "vehicles/search", params=params)
        return response.get("vehicles", [])

    async def get_vehicle_details(self, vehicle_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific vehicle"""
        response = await self._make_request("GET", f"vehicles/{vehicle_id}")
        return response.get("vehicle", {})

    async def check_availability(
        self,
        vehicle_id: str,
        from_time: str,
        to_time: str
    ) -> bool:
        """Check if a vehicle is available for specific dates"""
        params = {
            "from_time": from_time,
            "to_time": to_time
        }
        response = await self._make_request("GET", f"vehicles/{vehicle_id}/availability", params=params)
        return response.get("available", False)

class AwardTravelAPIIntegrator:
    """Main integrator class that combines all API clients"""

    def __init__(self, config: Dict[str, str]):
        self.flight_client = FlightAPIClient(config.get("flight_api_key"))
        self.hotel_client = HotelAPIClient(config.get("hotel_api_key"))
        self.car_client = CarRentalAPIClient(config.get("car_api_key"))

    async def search_travel_options(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        guests: int = 1,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Search for complete travel options (flights + hotels + cars)"""
        results = {
            "flights": [],
            "hotels": [],
            "cars": [],
            "metadata": {
                "search_time": datetime.utcnow().isoformat(),
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date
            }
        }

        # Search flights
        try:
            flights = await self.flight_client.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                adults=guests,
                currency=currency
            )
            results["flights"] = flights
        except Exception as e:
            logger.error(f"Flight search failed: {str(e)}")
            results["flights_error"] = str(e)

        # Search hotels
        try:
            check_in = departure_date
            check_out = return_date if return_date else (datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

            hotels = await self.hotel_client.search_hotels(
                location=destination,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                currency=currency
            )
            results["hotels"] = hotels
        except Exception as e:
            logger.error(f"Hotel search failed: {str(e)}")
            results["hotels_error"] = str(e)

        # Search cars
        try:
            from_time = f"{departure_date}T09:00:00"
            to_time = f"{return_date}T17:00:00" if return_date else (datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%dT17:00:00")

            cars = await self.car_client.search_vehicles(
                location=destination,
                from_time=from_time,
                to_time=to_time,
                limit=5
            )
            results["cars"] = cars
        except Exception as e:
            logger.error(f"Car search failed: {str(e)}")
            results["cars_error"] = str(e)

        return results

    async def get_travel_details(self, travel_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific travel option"""
        # In a real implementation, this would parse the travel_id and fetch details from appropriate services
        # For now, we'll return a mock structure
        return {
            "id": travel_id,
            "flights": [],
            "hotels": [],
            "cars": [],
            "total_price": 0,
            "award_points_required": 0
        }
