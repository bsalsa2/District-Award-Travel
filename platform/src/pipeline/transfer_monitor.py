import asyncio
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import redis

# Define the transfer bonus programs
PROGRAMS = {
    "Amex": "https://www.americanexpress.com/en-US/rewards/transfer-partners",
    "Chase": "https://www.chase.com/personal/credit-cards/travel-credit-cards/transfer-partners",
    "Citi": "https://www.citi.com/credit-cards/transfer-partners",
    "Capital One": "https://www.capitalone.com/credit-cards/transfer-partners"
}

# Define the Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

async def scrape_transfer_bonuses(program):
    response = requests.get(PROGRAMS[program])
    soup = BeautifulSoup(response.content, 'html.parser')
    bonuses = []
    for bonus in soup.find_all('div', class_='bonus'):
        bonus_name = bonus.find('h2').text.strip()
        bonus_percentage = bonus.find('span', class_='percentage').text.strip()
        bonus_expiration = bonus.find('span', class_='expiration').text.strip()
        bonuses.append({
            'program': program,
            'name': bonus_name,
            'percentage': bonus_percentage,
            'expiration': bonus_expiration
        })
    return bonuses

async def get_transfer_bonuses():
    bonuses = []
    tasks = [scrape_transfer_bonuses(program) for program in PROGRAMS]
    results = await asyncio.gather(*tasks)
    for result in results:
        bonuses.extend(result)
    return bonuses

async def save_transfer_bonuses(bonuses):
    with open('platform/data/transfer_bonuses.json', 'w') as f:
        json.dump(bonuses, f)

async def main():
    bonuses = await get_transfer_bonuses()
    await save_transfer_bonuses(bonuses)
    redis_client.set('transfer_bonuses', json.dumps(bonuses))

asyncio.run(main())
