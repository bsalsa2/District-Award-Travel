from typing import List, Optional
from datetime import datetime
from ..schemas.airline import FlightOfferResponse
from ...pipeline.scrapers import AirlineAPIScraper, FlightOffer
from ...config.airline_api_config import get_airline_api_config

class AirlineService:
    def __init__(self):
        self.config = get_airline_api_config()
        self.scraper = AirlineAPIScraper(self.config)

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: datetime,
        return_date: Optional[datetime] = None,
        cabin_class: str = "economy",
        adults: int = 1,
        max_stops: int = 1
    ) -> List[FlightOfferResponse]:
        """
        Search for flights using the airline API scraper
        """
        offers = await self.scraper.get_flight_offers(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            cabin_class=cabin_class,
            adults=adults,
            max_stops=max_stops
        )

        # Convert FlightOffer objects to response schema
        return [
            FlightOfferResponse(
                airline=offer.airline,
                flight_number=offer.flight_number,
                departure_time=offer.departure_time,
                arrival_time=offer.arrival_time,
                origin=offer.origin,
                destination=offer.destination,
                cabin_class=offer.cabin_class,
                price=offer.price,
                currency=offer.currency,
                offer_id=offer.offer_id,
                booking_url=offer.booking_url,
                duration=offer.duration,
                stops=offer.stops,
                fare_basis=offer.fare_basis,
                included_bags=offer.included_bags,
                timestamp=offer.timestamp
            )
            for offer in offers
        ]

    async def get_flight_status(
        self,
        airline: str,
        flight_number: str,
        departure_date: datetime,
        origin: str,
        destination: str
    ) -> Optional[dict]:
        """
        Get flight status from airline APIs
        """
        status = await self.scraper.get_flight_status(
            airline=airline,
            flight_number=flight_number,
            departure_date=departure_date,
            origin=origin,
            destination=destination
        )
        return status

    async def close(self):
        """Clean up resources"""
        await self.scraper.close()
