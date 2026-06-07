import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

# Load configuration from environment variables
SMTP_SERVER = os.environ['SMTP_SERVER']
SMTP_PORT = os.environ['SMTP_PORT']
SMTP_USERNAME = os.environ['SMTP_USERNAME']
SMTP_PASSWORD = os.environ['SMTP_PASSWORD']
SMS_API_KEY = os.environ['SMS_API_KEY']
SMS_API_SECRET = os.environ['SMS_API_SECRET']

# Load user profiles from database
def load_user_profiles():
    user_profiles = []
    with open('user_profiles.json', 'r') as f:
        user_profiles = json.load(f)
    return user_profiles

# Send email alert
def send_email_alert(user_email, award_flight_link):
    msg = MIMEMultipart()
    msg['From'] = 'Award Flight Alert System'
    msg['To'] = user_email
    msg['Subject'] = 'Award Flight Availability Alert'
    body = f'Award flight availability has opened up. Book now: {award_flight_link}'
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    text = msg.as_string()
    server.sendmail(SMTP_USERNAME, user_email, text)
    server.quit()

# Send SMS alert
def send_sms_alert(user_phone_number, award_flight_link):
    url = f'https://api.smsprovider.com/send?api_key={SMS_API_KEY}&api_secret={SMS_API_SECRET}&to={user_phone_number}&message=Award+flight+availability+has+opened+up.+Book+now%3A+{award_flight_link}'
    response = requests.get(url)
    if response.status_code != 200:
        print(f'Error sending SMS alert: {response.text}')

# Check award flight availability and send alerts
def check_award_flight_availability():
    user_profiles = load_user_profiles()
    for user_profile in user_profiles:
        user_email = user_profile['email']
        user_phone_number = user_profile['phone_number']
        preferred_airlines = user_profile['preferred_airlines']
        preferred_routes = user_profile['preferred_routes']
        # Check award flight availability for each preferred airline and route
        for airline in preferred_airlines:
            for route in preferred_routes:
                award_flight_link = f'https://example.com/award-flight/{airline}/{route}'
                # Simulate checking award flight availability
                if True:  # Replace with actual availability check
                    send_email_alert(user_email, award_flight_link)
                    send_sms_alert(user_phone_number, award_flight_link)

if __name__ == '__main__':
    check_award_flight_availability()
