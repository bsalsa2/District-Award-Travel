import numpy as np
from fastapi import HTTPException
from platform.src.intelligence.models import AwardPointsModel

class AwardPointsRedeemer:
    def __init__(self, award_points_model: AwardPointsModel):
        self.award_points_model = award_points_model

    def redeem_points(self, user_id: int, points_to_redeem: int):
        user_points = self.award_points_model.get_user_points(user_id)
        if user_points < points_to_redeem:
            raise HTTPException(status_code=400, detail="Insufficient points")
        self.award_points_model.update_user_points(user_id, user_points - points_to_redeem)
        return {"message": "Points redeemed successfully"}

    def get_user_points(self, user_id: int):
        return self.award_points_model.get_user_points(user_id)
