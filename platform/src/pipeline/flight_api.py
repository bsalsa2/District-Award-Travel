import requests
import numpy as np
from fastapi import FastAPI, HTTPException
from typing import List, Dict

app = FastAPI()

def get_flight_data(flight_number: str, departure_date: str) -> Dict:
    """
    Retrieves real-time flight data from external API.
    
    Args:
    flight_number (str): The flight number.
    departure_date (str): The departure date in YYYY-MM-DD format.
    
    Returns:
    Dict: A dictionary containing the flight data.
    """
    url = f"https://api.example.com/flights/{flight_number}/{departure_date}"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=404, detail="Flight data not found")

def get_available_flights(origin: str, destination: str, departure_date: str) -> List[Dict]:
    """
    Retrieves a list of available flights from the external API.
    
    Args:
    origin (str): The origin airport code.
    destination (str): The destination airport code.
    departure_date (str): The departure date in YYYY-MM-DD format.
    
    Returns:
    List[Dict]: A list of dictionaries containing the available flight data.
    """
    url = f"https://api.example.com/flights/{origin}/{destination}/{departure_date}"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=404, detail="No available flights found")

@app.get("/flights/{flight_number}/{departure_date}")
async def read_flight_data(flight_number: str, departure_date: str):
    return get_flight_data(flight_number, departure_date)

@app.get("/flights/{origin}/{destination}/{departure_date}")
async def read_available_flights(origin: str, destination: str, departure_date: str):
    return get_available_flights(origin, destination, departure_date)
