import requests
import time
import logging

logging.basicConfig(level=logging.INFO)

def fetch_award_availability(airline_api_key, airline_code, route):
    url = f"https://api.airline.com/award-availability?airline_code={airline_code}&route={route}"
    headers = {"Authorization": f"Bearer {airline_api_key}"}
    response = requests.get(url, headers=headers)
    return response.json()

def update_award_search_system(award_search_system_url, award_availability):
    url = f"{award_search_system_url}/update-award-availability"
    response = requests.post(url, json=award_availability)
    return response.status_code == 200

def main():
    airline_api_key = os.environ["AIRLINE_API_KEY"]
    award_search_system_url = os.environ["AWARD_SEARCH_SYSTEM_URL"]
    airline_code = "AA"
    route = "JFK-LAX"

    while True:
        award_availability = fetch_award_availability(airline_api_key, airline_code, route)
        if update_award_search_system(award_search_system_url, award_availability):
            logging.info("Award availability updated successfully")
        else:
            logging.error("Failed to update award availability")
        time.sleep(60)

if __name__ == "__main__":
    main()
