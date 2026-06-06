from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from platform.src.pipeline.booking_pipeline import BookingPipeline
from platform.src.intelligence.travel_booking_model import TravelBookingModel

app = FastAPI()

origins = [
    "http://localhost:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

booking_pipeline = BookingPipeline()
travel_booking_model = TravelBookingModel()

@app.post("/book_travel")
async def book_travel(request: Request):
    data = await request.json()
    result = booking_pipeline.book_travel(data)
    return JSONResponse(content=result, media_type="application/json")

@app.get("/travel_options")
async def get_travel_options():
    options = travel_booking_model.get_travel_options()
    return JSONResponse(content=options, media_type="application/json")
