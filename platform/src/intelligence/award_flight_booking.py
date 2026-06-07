import numpy as np

class AwardFlightBooking:
    def __init__(self, booking_id: str, passenger_name: str, flight_number: str, departure_date: str, return_date: str):
        self.booking_id = booking_id
        self.passenger_name = passenger_name
        self.flight_number = flight_number
        self.departure_date = departure_date
        self.return_date = return_date

    def __str__(self):
        return f"Booking ID: {self.booking_id}, Passenger Name: {self.passenger_name}, Flight Number: {self.flight_number}, Departure Date: {self.departure_date}, Return Date: {self.return_date}"
