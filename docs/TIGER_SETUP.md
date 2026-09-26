# Tiger Cloud setup — Milestone 4

Temple Twin expects a real Tiger Cloud PostgreSQL service.

## 1. Create the service

Create a Tiger Cloud service with time-series / real-time analytics enabled.

Collect:

- host
- port
- database
- username
- password

Tiger Cloud is PostgreSQL-compatible. Use SSL.

## 2. Configure the connection

Add this to your local `.env` (never commit the real value):

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

## 3. Install backend dependencies

```bash
python -m pip install -r backend/requirements.txt
```

## 4. Create schema + seed Tiger

From the repo root:

```bash
python scripts/seed_database.py
```

This creates:

- `buildings`
- `weather_hourly` hypertable
- `building_hourly_state` hypertable

and seeds 24 baseline Friday rows for SERC, Beury, and Engineering using the
actual ComStock-derived Milestone 3 profiles.

The command verifies that each building has exactly 24 rows before exiting.

## 5. Run FastAPI

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/buildings/serc/profile
curl "http://127.0.0.1:8000/api/buildings/serc/state?hour=14"
```

Expected profile contract: 24 records ordered by timestamp.

## Scientific status

Tiger is the storage/query layer. It does not make the values measured Temple
meter data. Hourly shapes come from NREL ComStock; Temple building magnitudes
remain modeled/calibrated estimates.
