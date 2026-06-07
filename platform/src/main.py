from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from platform.src.intelligence.cancellation_policy import CancellationPolicy
from platform.src.pipeline.cancellation_pipeline import CancellationPipeline

app = FastAPI()

@app.post("/calculate-cancellation-fee")
async def calculate_cancellation_fee(request: Request):
    data = await request.json()
    booking_date = data['bookingDate']
    cancellation_date = data['cancellationDate']
    booking_price = data['bookingPrice']

    policy_config = {
        'free_cancellation_period': 7,
        'cancellation_fee_percentage': 0.1,
        'booking_price': booking_price
    }

    cancellation_policy = CancellationPolicy(policy_config)
    cancellation_fee = cancellation_policy.calculate_cancellation_fee(booking_date, cancellation_date)

    return JSONResponse(content={'cancellationFee': cancellation_fee}, media_type='application/json')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
