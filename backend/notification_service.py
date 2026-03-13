import pika
import json
import time

def start_consumer():
    retries = 10
    delay = 5
    connection = None
    
    # 1. Connect to RabbitMQ with retries
    for i in range(retries):
        try:
            rabbitmq_host = 'localhost' # Or from env if needed
            connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
            break
        except pika.exceptions.AMQPConnectionError:
            if i < retries - 1:
                print(f"[*] RabbitMQ not ready (attempt {i+1}/{retries}). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"[!] RabbitMQ connection failed after {retries} attempts.")
                return

    if not connection:
        return

    try:
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

        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[*] Stopping Consumer...")
    except Exception as e:
        print(f"[!] Notification Service error: {e}")
    finally:
        if connection and not connection.is_closed:
            connection.close()

if __name__ == "__main__":
    start_consumer()
