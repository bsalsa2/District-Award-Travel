import sqlite3
from platform.src.models import AwardFlightCancellation

class AwardFlightCancellationSystem:
    def __init__(self):
        self.conn = sqlite3.connect("award_flight_cancellations.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS award_flight_cancellations (
                id INTEGER PRIMARY KEY,
                award_flight_booking_id INTEGER,
                cancellation_date TEXT,
                refund_amount INTEGER
            )
        """)
        self.conn.commit()

    def cancel_award_flight(self, award_flight_booking):
        self.cursor.execute("""
            INSERT INTO award_flight_cancellations (award_flight_booking_id, cancellation_date, refund_amount)
            VALUES (?, ?, ?)
        """, (award_flight_booking.id, "2026-06-07", award_flight_booking.award_points))
        self.conn.commit()
        return AwardFlightCancellation(
            id=self.cursor.lastrowid,
            award_flight_booking_id=award_flight_booking.id,
            cancellation_date="2026-06-07",
            refund_amount=award_flight_booking.award_points
        )
