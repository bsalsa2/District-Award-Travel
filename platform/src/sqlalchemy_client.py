from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import AwardTravelData

class SQLAlchemyClient:
    def __init__(self):
        self.engine = create_engine("sqlite:///database.db")
        self.Session = sessionmaker(bind=self.engine)

    async def insert_data(self, data):
        session = self.Session()
        session.add(data)
        session.commit()
        session.close()
