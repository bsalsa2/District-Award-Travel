import sqlite3
from platform.src.intelligence.models import PaymentGatewayConfig

def get_payment_gateway_config():
    conn = sqlite3.connect("payment_gateway.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payment_gateway_config")
    config = cursor.fetchone()
    conn.close()
    return PaymentGatewayConfig(
        base_url=config[0],
        api_key=config[1]
    )
