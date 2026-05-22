import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import Award

class AwardSearchEngine:
    def __init__(self):
        self.engine = create_engine("sqlite:///awards.db")
        self.Session = sessionmaker(bind=self.engine)

    async def search(self, query):
        async with self.Session() as session:
            results = await session.execute(query)
            return [dict(result) for result in results]

    async def initialize(self):
        async with self.Session() as session:
            await session.execute("""
                CREATE TABLE IF NOT EXISTS awards (
                    id INTEGER PRIMARY KEY,
                    origin TEXT,
                    destination TEXT,
                    travel_date TEXT,
                    award_type TEXT,
                    award_level TEXT
                )
            """)
            await session.commit()
