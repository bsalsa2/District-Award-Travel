import os
import sys
import smtplib
from email.mime.text import MIMEText

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the alerting system configuration
ALERTING_SYSTEM_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'from_email': 'district.award.travel@example.com',
    'to_email': 'mitchell@example.com',
    'password': 'password'
}

def send_email(subject, body):
    """
    Send an email using the alerting system configuration.
    """
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = ALERTING_SYSTEM_CONFIG['from_email']
        msg['To'] = ALERTING_SYSTEM_CONFIG['to_email']
        server = smtplib.SMTP(ALERTING_SYSTEM_CONFIG['smtp_server'], ALERTING_SYSTEM_CONFIG['smtp_port'])
        server.starttls()
        server.login(ALERTING_SYSTEM_CONFIG['from_email'], ALERTING_SYSTEM_CONFIG['password'])
        server.sendmail(ALERTING_SYSTEM_CONFIG['from_email'], ALERTING_SYSTEM_CONFIG['to_email'], msg.as_string())
        server.quit()
        logging.info(f'Email sent successfully: {subject}')
    except smtplib.SMTPException as e:
        logging.error(f'Failed to send email: {e}')

def main():
    # Set up the alerting system server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class AlertingSystemHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            alert_data = eval(body.decode('utf-8'))
            subject = f'Alert: {alert_data["metric"]}'
            body = f'The {alert_data["metric"]} metric has exceeded the threshold of {alert_data["threshold"]}. The current value is {alert_data["value"]}.'
            send_email(subject, body)
            self.send_response(200)
            self.end_headers()
    server = HTTPServer(('localhost', 8081), AlertingSystemHandler)
    logging.info('Alerting system server started')
    server.serve_forever()

if __name__ == '__main__':
    main()
