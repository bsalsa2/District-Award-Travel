from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform.src.models import Client, Redemption
from platform.src.schemas import ClientRedemptionHistoryResponse

router = APIRouter()

# Create a database engine and session maker
engine = create_engine('sqlite:///district_award_travel.db')
Session = sessionmaker(bind=engine)

# Define the endpoint to retrieve a client's redemption history
@router.get("/clients/{client_id}/redemption-history", response_model=ClientRedemptionHistoryResponse)
async def get_client_redemption_history(client_id: int):
    # Create a database session
    session = Session()

    try:
        # Retrieve the client's redemption history
        client = session.query(Client).filter(Client.id == client_id).first()
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")

        redemptions = session.query(Redemption).filter(Redemption.client_id == client_id).all()

        # Create a response object
        response = {
            "client_id": client_id,
            "redemptions": [
                {
                    "id": redemption.id,
                    "award_flight_details": redemption.award_flight_details,
                    "travel_dates": redemption.travel_dates,
                    "points_redeemed": redemption.points_redeemed
                }
                for redemption in redemptions
            ]
        }

        # Return the response as JSON
        return JSONResponse(content=response, media_type="application/json")
    except Exception as e:
        # Handle any exceptions and return an error response
        return JSONResponse(content={"error": str(e)}, media_type="application/json", status_code=500)
    finally:
        # Close the database session
        session.close()
