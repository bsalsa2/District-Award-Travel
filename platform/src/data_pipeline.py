import asyncio
from platform.src.data_lake import DataLake
from platform.src.data_warehouse import DataWarehouse

class DataPipeline:
    def __init__(self):
        self.data_lake = DataLake()
        self.data_warehouse = DataWarehouse()

    async def ingest_data(self, data: dict):
        self.data_lake.insert_data(data)
        insights = self.process_data(data)
        self.data_warehouse.insert_insights(insights)

    def process_data(self, data: dict) -> dict:
        # Process data using Apache Spark or similar technologies
        # For demonstration purposes, we'll just return some sample insights
        return {
            "user_id": data["user_id"],
            "flight_id": data["flight_id"],
            "award_type": data["award_type"],
            "travel_date": data["travel_date"],
            "insights": "Sample insights"
        }
