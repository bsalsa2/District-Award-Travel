class AwardFlightBooking:
    def __init__(self, id, passenger_name, flight_number, departure_date, return_date, award_points):
        self.id = id
        self.passenger_name = passenger_name
        self.flight_number = flight_number
        self.departure_date = departure_date
        self.return_date = return_date
        self.award_points = award_points

class AwardFlightCancellation:
    def __init__(self, id, award_flight_booking_id, cancellation_date, refund_amount):
        self.id = id
        self.award_flight_booking_id = award_flight_booking_id
        self.cancellation_date = cancellation_date
        self.refund_amount = refund_amount
