import asyncio
import requests
from bs4 import BeautifulSoup
from platform.src.data_pipeline import DataPipeline

class Scraper:
    def __init__(self):
        self.data_pipeline = DataPipeline()

    async def scrape_award_availability(self):
        url = "https://example.com/award-availability"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        data = []
        for item in soup.find_all("div", class_="award-availability"):
            award_id = item.find("span", class_="award-id").text
            availability = item.find("span", class_="availability").text
            data.append({"award_id": award_id, "availability": availability})
        await self.data_pipeline.ingest_award_availability(data)

    async def scrape_award_pricing(self):
        url = "https://example.com/award-pricing"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        data = []
        for item in soup.find_all("div", class_="award-pricing"):
            award_id = item.find("span", class_="award-id").text
            price = item.find("span", class_="price").text
            data.append({"award_id": award_id, "price": price})
        await self.data_pipeline.ingest_award_pricing(data)
