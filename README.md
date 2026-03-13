# Social Live Feed | Dashboard Berbasis Event

Dashboard aktivitas media sosial real-time berperforma tinggi yang dibangun untuk mendemonstrasikan **Arsitektur Berbasis Event Asinkron** menggunakan RabbitMQ, Python, FastAPI, PostgreSQL, dan Next.js.

## Struktur Proyek
- **/backend** — Jembatan FastAPI + RabbitMQ
  - `socket_server.py` — Penghubung: konsumsi RabbitMQ → WebSocket, simpan ke DB
  - `activity_service.py` — Producer: kirim event sosial acak
  - `notification_service.py` — Konsumen terminal (untuk debugging)
  - `Dockerfile` — Gambar kontainer untuk backend
  - `requirements.txt` — Dependensi Python
- **/frontend** — Dashboard Next.js 14
  - `Dockerfile` — Build kontainer multi-tahap
- **/db** — File basis data (dimuat otomatis oleh Docker saat boot pertama)
  - `init.sql` — Skema tabel (`users`, `social_events`)
  - `seed.sql` — Sampel pengguna & 12 event awal
- `docker-compose.yml` — Orkestrasi untuk ke-4 layanan

---

## Panduan Cepat dengan Docker (Direkomendasikan)

> Membutuhkan Docker Desktop yang sudah terpasang dan berjalan.

```bash
# Build & jalankan semua layanan (db, rabbitmq, backend, frontend)
docker compose up --build

# Buka aplikasi
# open http://localhost:3000

# UI manajemen RabbitMQ
# open http://localhost:15672   # guest / guest
```

Pada **boot pertama**, PostgreSQL secara otomatis menjalankan `db/init.sql` (membuat tabel) kemudian `db/seed.sql` (memasukkan data sampel).

### Verifikasi basis data
```bash
# List sampel pengguna
docker exec socialfeed_db psql -U postgres -d socialdb -c "SELECT * FROM users;"

# List sampel event
docker exec socialfeed_db psql -U postgres -d socialdb \
  -c "SELECT id, \"user\", action, target, timestamp FROM social_events;"
```

### Memicu event secara manual
```bash
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"user":"Alice","action":"liked","target":"Post #101","target_user":"Bob","timestamp":"12:00:00"}'
```

### Menghentikan layanan
```bash
docker compose down          # Tetap simpan volume DB
docker compose down -v       # Hapus juga data DB (seed ulang saat dijalankan lagi)
```

---

## Pengembangan Lokal (Tanpa Docker)

### 1. Persyaratan
- RabbitMQ berjalan secara lokal
- PostgreSQL berjalan secara lokal (database `socialdb`)
- Python 3.11+ dan Node 20+

```bash
# Jalankan RabbitMQ
docker run -d --name rabbitmq-local -p 5672:5672 rabbitmq:3-management

# Buat DB lokal dan masukkan seed
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

### 4. Jalankan pengujian event
```bash
cd backend
python activity_service.py
```

---

## Konsep Teknis

### Asinkron vs. Sinkron

| Fitur | Sinkron (REST) | Asinkron (RabbitMQ) |
| :--- | :--- | :--- |
| **Blocking** | Producer menunggu Consumer. | Producer mengirim dan lanjut bekerja. |
| **Coupling** | Layanan harus aktif bersamaan. | Layanan terpisah melalui broker. |
| **Resiliensi** | Permintaan gagal jika layanan mati. | Pesan antri sampai layanan aktif kembali. |
| **Skala** | Sulit diskalakan saat beban melonjak. | Mudah diskalakan dengan menambah konsumen. |

### Konsep

Aplikasi ini adalah **Social Live Feed** yang menggunakan arsitektur **Berbasis Event (Event-Driven)**. Konsep utamanya adalah memisahkan pengirim pesan (**Producer**) dan penerima pesan (**Consumer**) menggunakan **RabbitMQ** sebagai perantara (Message Broker). Hal ini memungkinkan aplikasi untuk menangani ribuan notifikasi secara real-time tanpa membebani server utama, karena setiap aktivitas diproses secara asinkron di latar belakang.

### Implementasi: Notifikasi RabbitMQ

Sistem notifikasi pada aplikasi ini diimplementasikan menggunakan model **Pub/Sub (Publish/Subscribe)** dengan tipe exchange `fanout`.

1.  **Producer (`activity_service.py`)**: Bertugas memicu event sosial (seperti *like*, *comment*, *share* secara acak). Setiap event dikirim ke exchange `social_events`.
2.  **Exchange (`fanout`)**: RabbitMQ akan menduplikasi pesan dari producer ke setiap antrian (**Queue**) yang terikat padanya.
3.  **Consumer (`notification_service.py` & `socket_server.py`)**:
    *   `notification_service.py` adalah konsumen sederhana yang menampilkan notifikasi di terminal untuk keperluan debugging/monitoring.
    *   `socket_server.py` mengonsumsi pesan dari RabbitMQ, menyimpannya ke database PostgreSQL, dan meneruskannya ke frontend melalui **WebSocket** secara real-time.

Dengan RabbitMQ, jika layanan notifikasi sedang sibuk atau mati, pesan akan tetap tersimpan di antrian hingga layanan tersebut siap memprosesnya kembali, menjaga sistem tetap tangguh (**Resilient**).

### Penggunaan AI Generatif

Proyek ini dikembangkan dengan bantuan **AI Generatif** untuk mengoptimalkan berbagai aspek teknis, antara lain:
- **Arsitektur Sistem**: Membantu perancangan alur kerja *event-driven* dan integrasi antar komponen.
- **Implementasi Backend**: Mempercepat penulisan logika producer/consumer RabbitMQ dan integrasi WebSocket.
- **Optimasi Database**: Membantu penyusunan skema relasional di PostgreSQL dan skrip seeding data.
- **Desain UI/UX**: Memberikan saran gaya desain modern dan implementasi komponen menggunakan Tailwind CSS untuk tampilan yang premium.

### Arsitektur
```
[Activity Service] ──publish──▶ [RabbitMQ] ──consume──▶ [Socket Server]
                                                                │
                                                     ┌──────────┴──────────┐
                                                     ▼                     ▼
                                               [PostgreSQL]         [WebSocket]
                                               (persisten)          (real-time)
                                                                        │
                                                                   [Next.js UI]
```
