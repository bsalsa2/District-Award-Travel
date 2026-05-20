import os
import json
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
import redis
import requests
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import structlog
from prometheus_client import make_wsgi_app, Counter, Gauge
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Initialize Flask app
app = Flask(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('notification_requests_total', 'Total notification requests')
ALERTS_PROCESSED = Counter('alerts_processed_total', 'Total alerts processed')
NOTIFICATIONS_SENT = Counter('notifications_sent_total', 'Total notifications sent', ['channel'])
ACTIVE_ALERTS = Gauge('active_alerts', 'Number of active alerts')

# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory()
)

logger = structlog.get_logger()

# Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))

# Initialize notification clients
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

sendgrid_client = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))

slack_client = WebClient(token=os.getenv('SLACK_TOKEN'))

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        # Check Redis connection
        redis_client.ping()

        # Check external services
        requests.get(os.getenv('ALERTMANAGER_URL', 'http://alert-manager:9093') + '/-/healthy', timeout=5)

        return jsonify({"status": "healthy", "timestamp": logging.Formatter.formatTime(logging.Formatter())}), 200
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# Alert processing endpoint
@app.route('/api/v1/alerts', methods=['POST'])
def receive_alert():
    REQUEST_COUNT.inc()

    try:
        alert_data = request.get_json()
        logger.info("Received alert", alert=alert_data)

        # Store alert in Redis
        alert_id = redis_client.incr('alert:counter')
        redis_client.hset(f'alert:{alert_id}', mapping={
            'data': json.dumps(alert_data),
            'status': 'received',
            'created_at': str(logging.Formatter.formatTime(logging.Formatter()))
        })

        # Process the alert
        process_alert(alert_data, alert_id)

        ALERTS_PROCESSED.inc()
        ACTIVE_ALERTS.inc()

        return jsonify({"status": "received", "alert_id": alert_id}), 202
    except Exception as e:
        logger.error("Failed to process alert", error=str(e))
        return jsonify({"error": str(e)}), 500

def process_alert(alert_data, alert_id):
    """Process an alert and send notifications through appropriate channels"""
    severity = alert_data.get('severity', 'warning').lower()
    message = alert_data.get('message', 'No message provided')
    recipients = alert_data.get('recipients', [])

    # Determine notification channels based on severity
    channels = ['email']  # Default channel

    if severity in ['critical', 'high']:
        channels.extend(['sms', 'slack'])

    # Send notifications through each channel
    for channel in channels:
        try:
            if channel == 'email':
                send_email_notification(alert_data, recipients)
            elif channel == 'sms':
                send_sms_notification(alert_data, recipients)
            elif channel == 'slack':
                send_slack_notification(alert_data)

            NOTIFICATIONS_SENT.labels(channel=channel).inc()
            logger.info(f"Notification sent via {channel}", alert_id=alert_id)

        except Exception as e:
            logger.error(f"Failed to send {channel} notification",
                        alert_id=alert_id, error=str(e))

    # Update alert status
    redis_client.hset(f'alert:{alert_id}', mapping={
        'status': 'processed',
        'processed_at': str(logging.Formatter.formatTime(logging.Formatter()))
    })

def send_email_notification(alert_data, recipients):
    """Send email notifications via SendGrid"""
    if not recipients or not os.getenv('SENDGRID_API_KEY'):
        return

    subject = f"[District Award Travel] Alert: {alert_data.get('alertname', 'Unknown')}"
    html_content = f"""
    <html>
        <body>
            <h2>Alert Notification</h2>
            <p><strong>Alert:</strong> {alert_data.get('alertname', 'Unknown')}</p>
            <p><strong>Severity:</strong> {alert_data.get('severity', 'warning').upper()}</p>
            <p><strong>Message:</strong> {alert_data.get('message', 'No message')}</p>
            <p><strong>Timestamp:</strong> {alert_data.get('startsAt', 'Unknown')}</p>
            <p>This is an automated notification from District Award Travel monitoring system.</p>
        </body>
    </html>
    """

    for recipient in recipients:
        try:
            message = Mail(
                from_email='alerts@district-award-travel.com',
                to_emails=recipient,
                subject=subject,
                html_content=html_content
            )
            response = sendgrid_client.send(message)
            logger.info("Email sent", recipient=recipient, status=response.status_code)
        except Exception as e:
            logger.error("Failed to send email", recipient=recipient, error=str(e))
            raise

def send_sms_notification(alert_data, recipients):
    """Send SMS notifications via Twilio"""
    if not recipients or not os.getenv('TWILIO_ACCOUNT_SID'):
        return

    message_body = f"DAT Alert: {alert_data.get('alertname', 'Unknown')} - {alert_data.get('severity', 'warning').upper()}: {alert_data.get('message', 'No message')}"

    for recipient in recipients:
        try:
            message = twilio_client.messages.create(
                body=message_body,
                from_=os.getenv('TWILIO_PHONE_NUMBER'),
                to=recipient
            )
            logger.info("SMS sent", recipient=recipient, sid=message.sid)
        except Exception as e:
            logger.error("Failed to send SMS", recipient=recipient, error=str(e))
            raise

def send_slack_notification(alert_data):
    """Send Slack notifications"""
    if not os.getenv('SLACK_TOKEN'):
        return

    severity_emoji = {
        'critical': ':rotating_light:',
        'high': ':fire:',
        'warning': ':warning:',
        'info': ':information_source:'
    }

    channel = '#alerts'
    emoji = severity_emoji.get(alert_data.get('severity', 'warning').lower(), ':warning:')

    try:
        response = slack_client.chat_postMessage(
            channel=channel,
            text=f"{emoji} *New Alert* {emoji}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} District Award Travel Alert {emoji}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Alert Name:*\n{alert_data.get('alertname', 'Unknown')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{alert_data.get('severity', 'warning').upper()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Timestamp:*\n{alert_data.get('startsAt', 'Unknown')}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Message:*\n{alert_data.get('message', 'No message provided')}"
                    }
                }
            ]
        )
        logger.info("Slack notification sent", channel=channel, ts=response['ts'])
    except SlackApiError as e:
        logger.error("Failed to send Slack notification", error=str(e))
        raise

if __name__ == '__main__':
    # Set up logging
    handler = RotatingFileHandler(
        '/var/log/notification-service/app.log',
        maxBytes=10485760,
        backupCount=5
    )
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    # Run the app
    app.run(host='0.0.0.0', port=8080, debug=False)
