import requests
from bs4 import BeautifulSoup
import json

def scrape_award_travel_data():
    url = "https://example.com/award-travel"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    data = []
    for item in soup.find_all('div', {'class': 'award-travel-item'}):
        data.append({
            'title': item.find('h2').text.strip(),
            'description': item.find('p').text.strip()
        })
    return data

def send_data_to_api(data):
    api_url = "http://api:8000/award-travel"
    response = requests.post(api_url, json=data)
    if response.status_code == 200:
        print("Data sent to API successfully!")
    else:
        print("Error sending data to API:", response.text)

def main():
    data = scrape_award_travel_data()
    send_data_to_api(data)

if __name__ == "__main__":
    main()
