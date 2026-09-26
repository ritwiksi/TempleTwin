# Tiger Cloud setup

Temple Twin uses a Tiger Cloud PostgreSQL-compatible service for campus metadata, weather, and 15-minute building-state storage.

## 1. Configure the connection

Add this to your local `.env`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

Never commit the real connection string.

## 2. Install backend dependencies

```bash
python -m pip install -r backend/requirements.txt
```

## 3. Create schema + seed Tiger

From the repo root:

```bash
python scripts/seed_database.py
```

The seed currently loads:

- 50 buildings;
- 8,736 15-minute baseline rows per building from Sep 1 through Nov 30, 2018 (436,800 building-state rows total);
- 2,184 hourly historical weather rows.

## 4. Run FastAPI

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Useful checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/buildings
curl http://127.0.0.1:8000/api/buildings/serc/profile
```

## Scientific status

Tiger is the storage/query layer. It does not turn modeled values into measured Temple meter data. Annual electricity is reported where an unambiguous public benchmarking match exists; other buildings use Temple's campus EUI calibration. The interactive 15-minute shapes come from NREL ComStock and the displayed weather spans the Sep 1–Nov 30, 2018 historical simulation window.
