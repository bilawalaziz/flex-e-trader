import pika
import json
from datetime import datetime, timedelta, timezone
import time
import random

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
EXCHANGE = "prices"
ROUTING_KEY = "prices.tick"

connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
channel = connection.channel()
channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)

product = "DE-AT-1700"
base_time = datetime(2026, 6, 12, 0, 0, tzinfo=timezone.utc)

try:
    while True:
        timestamp = base_time + timedelta(hours=len)
        msg = {
            "product": product,
            "timestamp": timestamp.isoformat(),
            "buy_price_eur_mwh": round(random.uniform(50, 100), 2),
            "sell_price_eur_mwh": round(random.uniform(55, 105), 2),
            "volume_mw": round(random.uniform(0, 200), 2),
        }
        channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            body=json.dumps(msg).encode(),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
        print(f"Sent: {msg}")
        time.sleep(5)
except KeyboardInterrupt:
    connection.close()
