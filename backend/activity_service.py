import pika
import json
import time
import random

def publish_event():
    # 1. Connect to RabbitMQ (localhost)
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # 2. Declare an exchange
    # Using 'fanout' simple broadcast for this demo
    exchange_name = 'social_events'
    channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')

    users = ["alice", "bob", "charlie", "david"]
    actions = ["liked", "commented on", "shared"]
    posts = ["Post #101", "Post #202", "Post #303"]

    print(f"[*] Activity Service started. Sending events to '{exchange_name}'...")

    try:
        while True:
            # Create a mock social event
            actor = random.choice(users)
            # Pick a target that is NOT the actor
            others = [u for u in users if u != actor]
            target_user = random.choice(others)

            event = {
                "user": actor,
                "action": random.choice(actions),
                "target": random.choice(posts),
                "target_user": target_user,
                "timestamp": time.strftime("%H:%M:%S")
            }
            
            message = json.dumps(event)
            
            # Publish the message
            channel.basic_publish(
                exchange=exchange_name,
                routing_key='', # Not needed for fanout
                body=message
            )
            
            print(f" [x] Sent: {event['user']} {event['action']} {event['target']}")
            
            # Wait a bit before next event
            time.sleep(random.uniform(1, 3))
            
    except KeyboardInterrupt:
        print("\n[*] Stopping Producer...")
    finally:
        connection.close()

if __name__ == "__main__":
    publish_event()
