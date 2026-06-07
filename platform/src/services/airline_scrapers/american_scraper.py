"""
American Airlines award flight scraper.
Optimized for AAdvantage program availability checks.
"""

from datetime import date
from typing import List, Optional
from bs4 import BeautifulSoup
from platform.src.models.award_flight import Airline, AwardFlight, FlightClass
from platform.src.services.airline_scrapers.base_scraper import BaseAirlineScraper

class AmericanAirlinesScraper(BaseAirlineScraper):
    """Scraper for American Airlines award availability."""

    def __init__(self):
        super().__init__(Airline.AA)
        self.base_url = "https://www.aa.com"

    async def check_award_availability(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        cabin_class: FlightClass = FlightClass.ECONOMY
    ) -> List[AwardFlight]:
        """Check AA award availability."""
        flights = []

        # Build search URL
        params = {
            "origin": origin,
            "destination": destination,
            "departureDate": departure_date.isoformat(),
            "cabin": cabin_class.value,
            "tripType": "roundtrip" if return_date else "oneway"
        }

        if return_date:
            params["returnDate"] = return_date.isoformat()

        url = f"{self.base_url}/reservation/searchFlights.do"
        html = await self._fetch(url, params)

        if not html:
            return flights

        soup = BeautifulSoup(html, 'html.parser')

        # Parse award availability (simplified - real implementation would need to handle dynamic content)
        # In production, we'd use Selenium or Playwright for dynamic content
        for row in soup.select(".award-availability-row"):
            try:
                flight_elem = row.select_one(".flight-number")
                if not flight_elem:
                    continue

                flight_number = self._clean_flight_number(flight_elem.text)

                miles_elem = row.select_one(".award-miles")
                miles_text = miles_elem.text.strip() if miles_elem else "0"
                award_miles = int("".join(filter(str.isdigit, miles_text)))

                availability_elem = row.select_one(".availability")
                availability = int(availability_elem.text.strip()) if availability_elem else 0

                flights.append(AwardFlight(
                    airline=self.airline,
                    flight_number=flight_number,
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    cabin_class=cabin_class,
                    award_miles=award_miles,
                    taxes_fees=50.00,  # Estimated
                    availability=availability,
                    booking_url=f"{self.base_url}/reservation/changeFlightRedirect.do?flightNumber={flight_number}",
                    last_updated=date.today()
                ))
            except Exception as e:
                continue

        return flights[:50]  # Limit results
