import asyncio
import requests
from bs4 import BeautifulSoup

async def fetch_airline_partnerships(airline):
    url = f'https://www.{airline}.com/partnerships'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    partnerships = [a.text.strip() for a in soup.find_all('a', href=True) if a.text.strip()]
    return partnerships

async def fetch_route_network(airline):
    url = f'https://www.{airline}.com/route-network'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    routes = [a.text.strip() for a in soup.find_all('a', href=True) if a.text.strip()]
    return routes
