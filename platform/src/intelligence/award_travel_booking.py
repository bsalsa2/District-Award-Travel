import numpy as np
from platform.src.pipeline.booking_pipeline import BookingPipeline

class AwardTravelBooking:
    def __init__(self):
        self.booking_pipeline = BookingPipeline()

    def book_award_travel(self, booking_pipeline):
        # Use AI model to predict award travel options
        award_travel_options = self.predict_award_travel_options()
        # Use booking pipeline to book award travel
        booking_id = self.booking_pipeline.book_award_travel(award_travel_options)
        return {"booking_id": booking_id}

    def predict_award_travel_options(self):
        # Use numpy to generate random award travel options
        award_travel_options = np.random.randint(0, 100, size=(5, 2))
        return award_travel_options

    def get_booking_status(self, booking_id: int):
        # Use booking pipeline to get booking status
        return self.booking_pipeline.get_booking_status(booking_id)
