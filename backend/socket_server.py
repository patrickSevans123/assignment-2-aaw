import asyncio
import json
import os
import threading
from typing import Optional, List
from datetime import datetime

import pika
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Configuration from env vars (Docker-friendly) ──────────
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
DATABASE_URL  = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/socialdb"
)

app = FastAPI(title="Social Live Feed — Bridge Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic Models ─────────────────────────────────────────
class PostCreate(BaseModel):
    username: str
    content: str

class CommentCreate(BaseModel):
    username: str
    content: str

class FollowRequest(BaseModel):
    follower: str
    following: str

# ── DB helpers ──────────────────────────────────────────────
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

def get_user_id(cursor, username: str) -> Optional[int]:
    cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
    row = cursor.fetchone()
    return row['id'] if row else None

def persist_event(event: dict):
    """Insert a social event into PostgreSQL."""
    try:
        conn = get_db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO social_events ("user", action, target, target_user, timestamp)
                    VALUES (%(user)s, %(action)s, %(target)s, %(target_user)s, %(timestamp)s)
                    """,
                    {
                        "user":        event.get("user"),
                        "action":      event.get("action"),
                        "target":      event.get("target"),
                        "target_user": event.get("target_user"),
                        "timestamp":   event.get("timestamp"),
                    },
                )
        conn.close()
    except Exception as exc:
        print(f"[!] DB persist error: {exc}")

def fetch_recent_events(limit: int = 50, target_user: str = None) -> list[dict]:
    """Return the most recent events from the DB, optionally filtered by target_user."""
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if target_user:
                cur.execute(
                    """
                    SELECT "user", action, target, target_user, timestamp
                    FROM   social_events
                    WHERE  LOWER(target_user) = LOWER(%s)
                    ORDER  BY id DESC
                    LIMIT  %s
                    """,
                    (target_user, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT "user", action, target, target_user, timestamp
                    FROM   social_events
                    ORDER  BY id DESC
                    LIMIT  %s
                    """,
                    (limit,),
                )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return list(reversed(rows))  # oldest first
    except Exception as exc:
        print(f"[!] DB fetch error: {exc}")
        return []

# ── WebSocket connection manager ────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# ── RabbitMQ helper ──────────────────────────────────────────
def get_rabbitmq_connection():
    """Attempt to connect to RabbitMQ with retries."""
    retries = 10
    delay = 5
    for i in range(retries):
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
        except pika.exceptions.AMQPConnectionError as e:
            if i < retries - 1:
                print(f"[*] RabbitMQ not ready (attempt {i+1}/{retries}). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"[!] RabbitMQ connection failed after {retries} attempts.")
                raise e

# ── RabbitMQ consumer (runs in background thread) ──────────
def rabbitmq_consumer():
    while True: # Outer loop for reconnection
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()

            exchange_name = "social_events"
            channel.exchange_declare(exchange=exchange_name, exchange_type="fanout")

            result     = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue
            channel.queue_bind(exchange=exchange_name, queue=queue_name)

            def callback(ch, method, properties, body):
                try:
                    message = body.decode()
                    event   = json.loads(message)

                    # Persist to DB
                    persist_event(event)

                    # Broadcast to WebSocket clients
                    asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
                except Exception as e:
                    print(f"[!] Error in consumer callback: {e}")

            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
            print(f"[*] Bridge Service started. Listening on RabbitMQ ({RABBITMQ_HOST})...")
            channel.start_consuming()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.ConnectionClosedByBroker) as e:
            print(f"[!] RabbitMQ connection lost: {e}. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[!] Unexpected error in rabbitmq_consumer: {e}. Restarting thread in 5s...")
            time.sleep(5)

@app.on_event("startup")
async def startup_event():
    # ── Clear seeded notifications from DB ──────────────────
    print("[*] Clearing persistent social events for a fresh start...")
    try:
        conn = get_db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE social_events")
        conn.close()
        print("[*] Social events cleared successfully.")
    except Exception as e:
        print(f"[!] Startup DB cleanup error: {e}")

    global loop
    loop = asyncio.get_event_loop()
    threading.Thread(target=rabbitmq_consumer, daemon=True).start()

# ── REST endpoints ──────────────────────────────────────────
@app.get("/events")
async def get_events(limit: int = 50, target_user: str = None):
    return fetch_recent_events(limit, target_user)

@app.post("/trigger")
async def trigger_event(event: dict):
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange="social_events", exchange_type="fanout")
        channel.basic_publish(
            exchange="social_events",
            routing_key="",
            body=json.dumps(event),
        )
        connection.close()
    except Exception as e:
        print(f"[!] Failed to trigger event: {e}")
        # We don't want to crash the whole request if notification fails, 
        # but the user should know something went wrong.
        pass
    return {"status": "event_triggered", "event": event}

# ── New Endpoints for Social Features ────────────────────────
@app.get("/users/{username}")
async def get_user_profile(username: str):
    conn = get_db_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get counts
        cur.execute("SELECT COUNT(*) FROM follows WHERE following_id = %s", (user['id'],))
        user['followers_count'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM follows WHERE follower_id = %s", (user['id'],))
        user['following_count'] = cur.fetchone()['count']
        
        # Get posts
        cur.execute("SELECT * FROM posts WHERE user_id = %s ORDER BY created_at DESC", (user['id'],))
        user['posts'] = [dict(r) for r in cur.fetchall()]
        
    conn.close()
    return user

@app.post("/posts")
async def create_post(post: PostCreate):
    conn = get_db_conn()
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            user_id = get_user_id(cur, post.username)
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")
            
            cur.execute(
                "INSERT INTO posts (user_id, content) VALUES (%s, %s) RETURNING id, created_at",
                (user_id, post.content)
            )
            new_post = cur.fetchone()
            
            # Notify followers
            cur.execute("SELECT u.username FROM users u JOIN follows f ON f.follower_id = u.id WHERE f.following_id = %s", (user_id,))
            followers = cur.fetchall()
            
            for f in followers:
                event = {
                    "user": post.username,
                    "action": "posted",
                    "target": f"a new post: \"{post.content[:20]}...\"",
                    "target_user": f['username'],
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                await trigger_event(event)
                
    conn.close()
    return {"status": "post_created", "post_id": new_post['id']}

@app.get("/posts")
async def get_all_posts():
    conn = get_db_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT p.id, p.content, p.created_at, u.username, u.display_name, u.avatar_url,
                   (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comments_count
            FROM posts p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
        """)
        posts = [dict(r) for r in cur.fetchall()]
    conn.close()
    return posts

@app.post("/posts/{post_id}/comments")
async def add_comment(post_id: int, comment: CommentCreate):
    print(f"[*] Adding comment to post {post_id} by {comment.username}")
    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                user_id = get_user_id(cur, comment.username)
                if not user_id:
                    print(f"[!] User {comment.username} not found")
                    raise HTTPException(status_code=404, detail="User not found")
                
                cur.execute(
                    "INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s) RETURNING id",
                    (post_id, user_id, comment.content)
                )
                
                # Notify post owner
                cur.execute("SELECT u.username FROM users u JOIN posts p ON p.user_id = u.id WHERE p.id = %s", (post_id,))
                owner = cur.fetchone()
                
                if owner and owner['username'].lower() != comment.username.lower():
                    event = {
                        "user": comment.username,
                        "action": "commented on",
                        "target": "your post",
                        "target_user": owner['username'],
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    print(f"[*] Triggering notification for {owner['username']}")
                    await trigger_event(event)

        return {"status": "comment_added"}
    except Exception as e:
        print(f"[!] Comment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/posts/{post_id}/like")
async def like_post(post_id: int, req: dict):
    username = req.get("username")
    print(f"[*] Liking post {post_id} by {username}")
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
        
    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 1. Get post owner
                cur.execute("SELECT u.username FROM users u JOIN posts p ON p.user_id = u.id WHERE p.id = %s", (post_id,))
                owner = cur.fetchone()
                
                if not owner:
                    raise HTTPException(status_code=404, detail="Post not found")
                
                # 2. Trigger notification if it's not the user's own post
                if owner['username'].lower() != username.lower():
                    event = {
                        "user": username,
                        "action": "liked",
                        "target": "your post",
                        "target_user": owner['username'],
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    print(f"[*] Triggering like notification for {owner['username']}")
                    await trigger_event(event)
                    
        return {"status": "liked"}
    except Exception as e:
        print(f"[!] Like error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/follow")
async def follow_user(req: FollowRequest):
    conn = get_db_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                follower_id = get_user_id(cur, req.follower)
                following_id = get_user_id(cur, req.following)
                
                if not follower_id or not following_id:
                    raise HTTPException(status_code=404, detail="User not found")
                
                cur.execute(
                    "INSERT INTO follows (follower_id, following_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (follower_id, following_id)
                )
                
                # Notify target
                event = {
                    "user": req.follower,
                    "action": "followed",
                    "target": "you",
                    "target_user": req.following,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                await trigger_event(event)
    except Exception as e:
        print(f"Follow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "followed"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
