from typing import Dict
from fastapi import HTTPException
from platform.src.intelligence.award_points import AwardPoints
from platform.src.intelligence.availability import Availability

class AwardBooking:
    def __init__(self, award_points: AwardPoints, availability: Availability):
        self.award_points = award_points
        self.availability = availability

    def book_award(self, user_id: int, award_id: int, points: int) -> Dict:
        if not self.availability.check_availability(award_id):
            raise HTTPException(status_code=400, detail="Award is not available")

        if not self.award_points.check_points(user_id, points):
            raise HTTPException(status_code=400, detail="Insufficient points")

        self.award_points.update_points(user_id, -points)
        self.availability.update_availability(award_id, -1)

        return {"message": "Award booked successfully"}
