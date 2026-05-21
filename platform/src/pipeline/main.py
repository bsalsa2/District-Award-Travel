from fastapi import FastAPI
from platform.src.pipeline.award_booking import AwardBooking
from platform.src.intelligence.award_points import AwardPoints
from platform.src.intelligence.availability import Availability

app = FastAPI()

@app.post("/book_award")
async def book_award(user_id: int, award_id: int, points: int):
    award_points = AwardPoints()
    availability = Availability()
    award_booking = AwardBooking(award_points, availability)
    return award_booking.book_award(user_id, award_id, points)
