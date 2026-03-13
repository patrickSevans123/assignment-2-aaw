# Social Live Feed | Event-Driven Dashboard

A high-performance, real-time social media activity dashboard built to demonstrate **Asynchronous Event-Driven Architecture** using RabbitMQ, Python, FastAPI, PostgreSQL, and Next.js.

## 📁 Project Structure
- **/backend** — FastAPI + RabbitMQ bridge
  - `socket_server.py` — Bridge: consumes RabbitMQ → WebSocket, persists to DB
  - `activity_service.py` — Producer: publishes random social events
  - `notification_service.py` — Console consumer (for debugging)
  - `Dockerfile` — Container image for the backend
  - `requirements.txt` — Python dependencies
- **/frontend** — Next.js 14 dashboard
  - `Dockerfile` — Multi-stage container build
- **/db** — Database files (auto-loaded by Docker on first boot)
  - `init.sql` — Table schema (`users`, `social_events`)
  - `seed.sql` — Sample users & 12 seed events
- `docker-compose.yml` — Orchestrates all 4 services

---

## 🐳 Quick Start with Docker (Recommended)

> Requires Docker Desktop installed and running.

```bash
# Build & start all services (db, rabbitmq, backend, frontend)
docker compose up --build

# Visit the app
open http://localhost:3000

# RabbitMQ management UI
open http://localhost:15672   # guest / guest
```

On **first boot**, PostgreSQL automatically runs `db/init.sql` (creates tables) then `db/seed.sql` (inserts sample data).

### Verify the database
```bash
# List seed users
docker exec socialfeed_db psql -U postgres -d socialdb -c "SELECT * FROM users;"

# List seed events
docker exec socialfeed_db psql -U postgres -d socialdb \
  -c "SELECT id, \"user\", action, target, timestamp FROM social_events;"
```

### Trigger an event manually
```bash
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"user":"Alice","action":"liked","target":"Post #101","target_user":"Bob","timestamp":"12:00:00"}'
```

### Stop everything
```bash
docker compose down          # Keep DB volume
docker compose down -v       # Also wipe DB data (fresh seed on next up)
```

---

## 🖥️ Local Development (without Docker)

### 1. Requirements
- RabbitMQ running locally
- PostgreSQL running locally (`socialdb` database)
- Python 3.11+ and Node 20+

```bash
# Start RabbitMQ
docker run -d --name rabbitmq-local -p 5672:5672 rabbitmq:3-management

# Create local DB and seed it
psql -U postgres -c "CREATE DATABASE socialdb;"
psql -U postgres -d socialdb -f db/init.sql
psql -U postgres -d socialdb -f db/seed.sql
```

### 2. Backend
```bash
cd backend
pip install -r requirements.txt
python socket_server.py
```

### 3. Frontend
```bash
cd frontend
pnpm install
pnpm run dev
```

### 4. Trigger test events
```bash
cd backend
python activity_service.py
```

---

## 💡 Technical Concepts

### Asynchronous vs. Synchronous

| Feature | Synchronous (REST) | Asynchronous (RabbitMQ) |
| :--- | :--- | :--- |
| **Blocking** | Producer waits for Consumer. | Producer sends and moves on. |
| **Coupling** | Services must be online together. | Services are decoupled via a broker. |
| **Resilience** | Request fails if service is down. | Messages are queued until service is back. |
| **Scale** | Harder to scale under spikes. | Easy to scale by adding more consumers. |

### Concept

Aplikasi ini adalah **Social Live Feed** yang menggunakan arsitektur **Event-Driven**. Konsep utamanya adalah memisahkan pengirim pesan (**Producer**) dan penerima pesan (**Consumer**) menggunakan **RabbitMQ** sebagai perantara (Message Broker). Hal ini memungkinkan aplikasi untuk menangani ribuan notifikasi secara real-time tanpa membebani server utama, karena setiap aktivitas diproses secara asinkron di latar belakang.

### Implementation: RabbitMQ Notification

Sistem notifikasi pada aplikasi ini diimplementasikan menggunakan model **Pub/Sub (Publish/Subscribe)** dengan tipe exchange `fanout`.

1.  **Producer (`activity_service.py`)**: Bertugas memicu event sosial (seperti *like*, *comment*, *share* secara acak). Setiap event dikirim ke exchange `social_events`.
2.  **Exchange (`fanout`)**: RabbitMQ akan menduplikasi pesan dari producer ke setiap antrian (**Queue**) yang terikat padanya.
3.  **Consumer (`notification_service.py` & `socket_server.py`)**:
    *   `notification_service.py` adalah consumer sederhana yang mencetak notifikasi ke terminal untuk keperluan debugging/monitoring.
    *   `socket_server.py` mengkonsumsi pesan dari RabbitMQ, menyimpannya ke database PostgreSQL, dan meneruskannya ke frontend melalui **WebSocket** secara real-time.

Dengan RabbitMQ, jika service notifikasi sedang sibuk atau mati, pesan akan tetap tersimpan di antrian hingga service tersebut siap memprosesnya kembali, menjaga sistem tetap tangguh (**Resilient**).

### Architecture
```
[Activity Service] ──publish──▶ [RabbitMQ] ──consume──▶ [Socket Server]
                                                               │
                                                    ┌──────────┴──────────┐
                                                    ▼                     ▼
                                              [PostgreSQL]         [WebSocket]
                                             (persistent)        (real-time)
                                                                       │
                                                                  [Next.js UI]
```
