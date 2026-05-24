import numpy as np
from fastapi import FastAPI
from platform.src.intelligence.award_points_redeemer import AwardPointsRedeemer
from platform.src.intelligence.models import AwardPointsModel

app = FastAPI()

@app.post("/redeem_points")
async def redeem_points(user_id: int, points_to_redeem: int):
    award_points_model = AwardPointsModel("award_points.db")
    award_points_redeemer = AwardPointsRedeemer(award_points_model)
    try:
        result = award_points_redeemer.redeem_points(user_id, points_to_redeem)
        return result
    except HTTPException as e:
        return {"error": str(e)}
    finally:
        award_points_model.close()

@app.get("/get_user_points")
async def get_user_points(user_id: int):
    award_points_model = AwardPointsModel("award_points.db")
    award_points_redeemer = AwardPointsRedeemer(award_points_model)
    try:
        points = award_points_redeemer.get_user_points(user_id)
        return {"points": points}
    except Exception as e:
        return {"error": str(e)}
    finally:
        award_points_model.close()
