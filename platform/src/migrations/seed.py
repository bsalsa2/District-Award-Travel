from platform.src.models.models import Session, Client, PointsBalance

def seed_database():
    session = Session()

    # Create sample clients
    client1 = Client(name='John Doe', email='john@example.com', phone='123-456-7890')
    client2 = Client(name='Jane Doe', email='jane@example.com', phone='987-654-3210')
    client3 = Client(name='Bob Smith', email='bob@example.com', phone='555-123-4567')

    # Create sample points balances
    points_balance1 = PointsBalance(client_id=1, program_name='Amex', balance=10000)
    points_balance2 = PointsBalance(client_id=1, program_name='Chase', balance=5000)
    points_balance3 = PointsBalance(client_id=2, program_name='United', balance=20000)
    points_balance4 = PointsBalance(client_id=3, program_name='Amex', balance=15000)
    points_balance5 = PointsBalance(client_id=3, program_name='Chase', balance=8000)
    points_balance6 = PointsBalance(client_id=3, program_name='United', balance=10000)

    # Add clients and points balances to the session
    session.add(client1)
    session.add(client2)
    session.add(client3)
    session.add(points_balance1)
    session.add(points_balance2)
    session.add(points_balance3)
    session.add(points_balance4)
    session.add(points_balance5)
    session.add(points_balance6)

    # Commit the changes
    session.commit()

    # Close the session
    session.close()

if __name__ == '__main__':
    seed_database()
