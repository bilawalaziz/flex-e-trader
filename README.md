# FlexiTrader – Energy Flexibility Optimisation Platform

**Real‑time data ingestion, algorithmic battery dispatch, and live trader dashboards**  

---

## 1. What problem does it solve?

Energy traders managing a portfolio of batteries, solar, wind, and biogas plants need to decide **every few minutes** how to charge, discharge, or ramp their flexible assets. Electricity prices change constantly, and physical constraints (battery capacity, efficiency, ramp rates) make manual planning impossible at scale.

FlexiTrader automates the entire loop:
- **Ingests** live market prices from multiple streams.
- **Validates** data and stores only the latest, clean snapshots.
- **Computes** optimal dispatch schedules using linear programming.
- **Exposes** schedules via REST APIs and real‑time WebSocket notifications.
- **Displays** everything in a live Grafana dashboard.

Result: traders see actionable recommendations updated every minute, without touching a spreadsheet.

---

## 2. High‑level architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│  Market     │      │  RabbitMQ   │      │  PostgreSQL  │
│  data feed  │─────▶│  (topic)    │─────▶│  (prices,    │
│  (simulated)│      │             │      │   schedules) │
└─────────────┘      └─────────────┘      └──────┬───────┘
                                                   │
                          ┌────────────────────────┤
                          │                        │
                    ┌─────▼─────┐          ┌──────▼──────┐
                    │  FastAPI  │          │  Celery     │
                    │  REST+WS  │◀─────────│  worker     │
                    └─────┬─────┘          │  (optimiser)│
                          │                └─────────────┘
                          │
                    ┌─────▼─────┐
                    │  Grafana  │
                    │  dashboard│
                    └───────────┘
```

- **RabbitMQ** decouples price producers from consumers.  
- **PostgreSQL** stores assets, prices, and computed schedules.  
- **Redis** powers real‑time WebSocket broadcasting.  
- **Celery** handles background optimisation tasks independently from the API.  
- **Grafana** provides a live multi‑asset dashboard with auto‑refresh.

---

## 3. Tech stack (exactly matches the job spec)

| Category        | Technology                                              |
|-----------------|---------------------------------------------------------|
| Language        | Python 3.12                                             |
| Async framework | asyncio, FastAPI, FastStream                            |
| ORM / DB        | SQLAlchemy (async), PostgreSQL                          |
| Data validation | Pydantic                                                |
| Optimisation    | pandas, scipy (linear programming)                      |
| Messaging       | RabbitMQ (topic exchange)                               |
| Caching / Pub‑Sub | Redis                                                  |
| Background tasks| Celery (beat + worker)                                  |
| Containerisation| Docker, docker‑compose                                   |
| CI/CD           | GitHub Actions, Terraform , Helm charts |
| Monitoring      | Grafana (PostgreSQL datasource, auto‑refresh)           |

---

## 4. Key features

### Data ingestion
- Receives JSON price ticks via RabbitMQ.
- Validates messages with Pydantic (malformed data rejected).
- Idempotent upsert with natural key `(product, timestamp)`.
- Out‑of‑order protection using `event_time` (only newer updates accepted).

### Optimisation engine
-  linear programming model (scipy `linprog`).
- Handles multiple batteries simultaneously.
- Respects: charge/discharge limits, capacity, efficiency, SoC bounds, mutual exclusivity.
- Output: time‑series schedule (power in MW, SoC in kWh) for every 15‑minute slot.

### Trader APIs
- `GET /api/v1/schedules/{asset_id}` – latest schedule.
- `POST /api/v1/schedules/{asset_id}` – manual override of a slot.
- `GET /api/v1/prices` – latest price curve.

### Real‑time WebSocket
- Endpoint `/ws/live` accepts browser connections.
- Redis pub‑sub bridges the scheduler and connected clients.
- Instant notification when a new schedule is computed.

### Automated background loop (Celery)
- Celery Beat triggers optimisation every 60 seconds.
- Celery Beat also publishes fresh test prices every 5 minutes → the demo never runs dry.

### Grafana live dashboard
- Multi‑asset dropdown (select any battery).
- Time‑series charts for power schedule and state of charge.
- Stat panels for latest market price and current battery SoC.
- Auto‑refresh every 5 seconds.

### DevOps & testing
- Multi‑stage Docker image (dependency caching).
- Alembic migrations run automatically on container start.
- pytest test suite (unit + integration) with dedicated test database.
- CI pipeline (GitHub Actions) runs tests, builds Docker image.

---

## 5. How to run the demo

### Prerequisites
- Docker & docker‑compose installed.
- Ports 8000 (API), 3000 (Grafana), 15672 (RabbitMQ UI) free.

### Start everything
```bash
docker-compose up --build -d
```

This launches:
- `app` – FastAPI server
- `postgres` – database
- `rabbitmq` – message broker
- `redis` – pub‑sub
- `celery-worker` – runs optimisation & price publishing
- `celery-beat` – triggers periodic tasks
- `grafana` – dashboards

### Seed a battery asset (one‑time)
```bash
docker-compose exec postgres psql -U flextrader -d flextrader -c "
INSERT INTO assets (name, type, max_charge_mw, max_discharge_mw, capacity_kwh, charge_efficiency, discharge_efficiency, min_soc, max_soc)
VALUES ('Battery1', 'battery', 5, 5, 5000, 0.95, 0.95, 0.1, 0.9);
"
```

### Verify everything works

- Health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- After ~60 seconds, the optimiser will run and produce a schedule.
- View the schedule: `http://localhost:8000/api/v1/schedules/1`
- Live dashboard: `http://localhost:3000/d/flextrader` (admin/admin)
- Open `dashboard.html` in your browser to see Grafana + live WebSocket updates.

---

## 6. my future work 

- **Redis caching** for frequently‑accessed price curves.
- **A MILP formulation** of the charge/discharge exclusivity constraint. The
  solver currently solves the LP relaxation and then repairs any interval where
  both flows came back non‑zero, by zeroing the smaller and recomputing the SOC
  trajectory. That keeps the schedule physically feasible but not provably
  optimal.
- **Prometheus metrics.** Grafana reads Postgres directly today; the service
  itself is not instrumented.
- **A hosted deployment.** The Terraform and Helm setup targets a local kind
  cluster through kubeconfig; nothing runs in a cloud environment yet.
- **User authentication** for trader APIs.
- **Historical trend analysis** endpoints.
- **Email / Slack alerts** on schedule changes.
- **Extended model** for solar, wind, and biogas plants (multi‑asset full portfolio).

---

## 7. Project structure (key directories)

```
app/
├── api/               # FastAPI routes + WebSocket
├── consumers/         # RabbitMQ subscribers (FastStream)
├── models/            # SQLAlchemy models (Asset, Price, Schedule)
├── repositories/      # Database access (upsert logic)
├── schemas/           # Pydantic DTOs
├── services/          # Business logic (optimisation, scheduler)
├── celery_app.py      # Celery configuration & beat schedule
├── tasks.py           # Celery tasks (optimisation, publishing)
tests/                 # pytest suite
scripts/               # Price tick producer (CLI)
grafana/               # Dashboard & datasource provisioning
infra/                 # Terraform + Helm charts, kind cluster config
.github/workflows/     # CI: migrations, tests, Docker build
```

---
