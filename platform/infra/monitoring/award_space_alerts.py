import pika
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RabbitMQ connection settings
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_QUEUE = 'award_space_alerts'

# Connect to RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT))
channel = connection.channel()
channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

def send_alert(alert_data):
    """
    Send an alert notification to the RabbitMQ queue.
    """
    try:
        channel.basic_publish(exchange='',
                              routing_key=RABBITMQ_QUEUE,
                              body=json.dumps(alert_data),
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                              ))
        logger.info(f"Sent alert: {alert_data}")
    except Exception as e:
        logger.error(f"Error sending alert: {e}")

def process_award_space_update(data):
    """
    Process an award space update and send an alert if necessary.
    """
    # Check if the award space has changed
    if data['award_space_available'] != data['previous_award_space_available']:
        alert_data = {
            'award_space_id': data['award_space_id'],
            'new_award_space_available': data['award_space_available'],
            'previous_award_space_available': data['previous_award_space_available']
        }
        send_alert(alert_data)

# Example usage
if __name__ == '__main__':
    data = {
        'award_space_id': 123,
        'award_space_available': 10,
        'previous_award_space_available': 5
    }
    process_award_space_update(data)
