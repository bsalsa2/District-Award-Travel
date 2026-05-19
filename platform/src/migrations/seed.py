from platform.src.models.models import Base, Client, PointsBalance
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def seed_database():
    engine = create_engine('sqlite:///platform.db')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    client1 = Client(name='John Doe', email='john@example.com', phone='123-456-7890')
    client2 = Client(name='Jane Doe', email='jane@example.com', phone='987-654-3210')
    client3 = Client(name='Bob Smith', email='bob@example.com', phone='555-123-4567')

    session.add(client1)
    session.add(client2)
    session.add(client3)

    points_balance1 = PointsBalance(client_id=1, program_name='Program 1', balance=1000.0, last_updated='2026-05-19 00:00:00')
    points_balance2 = PointsBalance(client_id=2, program_name='Program 2', balance=2000.0, last_updated='2026-05-19 00:00:00')
    points_balance3 = PointsBalance(client_id=3, program_name='Program 3', balance=3000.0, last_updated='2026-05-19 00:00:00')

    session.add(points_balance1)
    session.add(points_balance2)
    session.add(points_balance3)

    session.commit()

if __name__ == '__main__':
    seed_database()
