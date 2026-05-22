from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import numpy as np
from typing import Dict

app = FastAPI()

# Define a function to process user input
def process_input(input_text: str):
    # Tokenize the input text
    tokens = input_text.split()
    # Determine the intent of the user
    if 'book' in tokens:
        return 'book_flight'
    elif 'get' in tokens and 'bookings' in tokens:
        return 'get_bookings'
    else:
        return 'unknown'

# Define a route to process user input
@app.post('/process_input')
async def process_input_route(request: Request):
    data = await request.json()
    input_text = data['input_text']
    intent = process_input(input_text)
    return JSONResponse({'intent': intent}, status_code=200)

# Define a function to generate a response
def generate_response(intent: str, user_id: int):
    if intent == 'book_flight':
        return 'Please provide the flight details.'
    elif intent == 'get_bookings':
        # Get the bookings for the user
        bookings = get_bookings(user_id)
        return 'You have the following bookings: ' + ', '.join([f'Booking {booking[0]}: Flight {booking[2]} on {booking[3]}' for booking in bookings])
    else:
        return 'I did not understand your request.'

# Define a route to generate a response
@app.post('/generate_response')
async def generate_response_route(request: Request):
    data = await request.json()
    intent = data['intent']
    user_id = data['user_id']
    response = generate_response(intent, user_id)
    return JSONResponse({'response': response}, status_code=200)
