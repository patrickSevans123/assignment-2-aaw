import pika
import json
import time

def start_consumer():
    # 1. Connect to RabbitMQ (localhost)
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # 2. Declare the same exchange
    exchange_name = 'social_events'
    channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')

    # 3. Create a temporary queue unique to this consumer
    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    # 4. Bind the queue to the exchange
    channel.queue_bind(exchange=exchange_name, queue=queue_name)

    print(f"[*] Notification Service started. Waiting for events. To exit press CTRL+C")

    def callback(ch, method, properties, body):
        event = json.loads(body)
        print(f" [!] NOTIFICATION: [{event['timestamp']}] {event['user']} {event['action']} {event['target']}")
        
        # Simulate processing time
        time.sleep(0.5)

    # 5. Start consuming
    channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback,
        auto_ack=True
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[*] Stopping Consumer...")
        connection.close()

if __name__ == "__main__":
    start_consumer()
