import asyncio
import requests
from bs4 import BeautifulSoup

class AwardScraper:
    def __init__(self):
        pass

    async def scrape(self, url: str):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        awards = []
        for award in soup.find_all("div", class_="award"):
            origin = award.find("span", class_="origin").text
            destination = award.find("span", class_="destination").text
            travel_date = award.find("span", class_="travel-date").text
            award_type = award.find("span", class_="award-type").text
            award_level = award.find("span", class_="award-level").text
            awards.append({
                "origin": origin,
                "destination": destination,
                "travel_date": travel_date,
                "award_type": award_type,
                "award_level": award_level
            })
        return awards

async def main():
    scraper = AwardScraper()
    url = "https://example.com/awards"
    awards = await scraper.scrape(url)
    print(awards)

if __name__ == "__main__":
    asyncio.run(main())
