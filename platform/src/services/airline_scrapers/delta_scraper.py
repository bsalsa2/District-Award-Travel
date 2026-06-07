"""
Delta Air Lines award flight scraper.
Optimized for SkyMiles program availability checks.
"""

from datetime import date
from typing import List, Optional
from bs4 import BeautifulSoup
import re
from platform.src.models.award_flight import Airline, AwardFlight, FlightClass
from platform.src.services.airline_scrapers.base_scraper import BaseAirlineScraper

class DeltaAirlinesScraper(BaseAirlineScraper):
    """Scraper for Delta Air Lines award availability."""

    def __init__(self):
        super().__init__(Airline.DL)
        self.base_url = "https://www.delta.com"

    async def check_award_availability(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        cabin_class: FlightClass = FlightClass.ECONOMY
    ) -> List[AwardFlight]:
        """Check Delta award availability."""
        flights = []

        # Delta uses a different approach - we'll simulate API calls
        # In production, this would be actual API calls with proper authentication
        params = {
            "origin": origin,
            "destination": destination,
            "departureDate": departure_date.isoformat(),
            "returnDate": return_date.isoformat() if return_date else "",
            "cabin": cabin_class.value.lower()
        }

        url = f"{self.base_url}/booking/shop/awardFlights"
        html = await self._fetch(url, params)

        if not html:
            return flights

        # Parse JSON response (simplified)
        try:
            import json
            data = json.loads(html)

            for flight_data in data.get("flights", []):
                try:
                    flight_number = flight_data.get("flightNumber", "").strip()
                    if not flight_number:
                        continue

                    # Extract airline from flight number
                    airline_code = flight_number[:2]
                    if airline_code != self.airline:
                        continue

                    award_miles = flight_data.get("awardMiles", 0)
                    availability = flight_data.get("seatsAvailable", 0)

                    flights.append(AwardFlight(
                        airline=self.airline,
                        flight_number=flight_number,
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                        cabin_class=cabin_class,
                        award_miles=award_miles,
                        taxes_fees=55.60,  # Estimated
                        availability=availability,
                        booking_url=f"{self.base_url}/booking/shop/flightDetails?flightNumber={flight_number}",
                        last_updated=date.today()
                    ))
                except Exception:
                    continue

        except json.JSONDecodeError:
            # Fallback to HTML parsing if JSON fails
            soup = BeautifulSoup(html, 'html.parser')
            for row in soup.select(".flight-row"):
                try:
                    flight_number = row.select_one(".flight-num").text.strip()
                    if not flight_number.startswith(self.airline):
                        continue

                    award_miles = int(row.select_one(".miles").text.strip().replace(",", ""))
                    availability = int(row.select_one(".seats").text.strip())

                    flights.append(AwardFlight(
                        airline=self.airline,
                        flight_number=flight_number,
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                        cabin_class=cabin_class,
                        award_miles=award_miles,
                        taxes_fees=55.60,
                        availability=availability,
                        booking_url=f"{self.base_url}/booking/shop/flightDetails?flightNumber={flight_number}",
                        last_updated=date.today()
                    ))
                except Exception:
                    continue

        return flights[:50]
