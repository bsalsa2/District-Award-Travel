from pydantic import BaseModel

class ClientRedemptionHistoryResponse(BaseModel):
    client_id: int
    redemptions: list[dict]
