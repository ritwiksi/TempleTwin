# Temple Twin

Temple Twin is a 3D campus energy digital twin for Temple University's Main Campus.

It combines Temple GIS building geometry and floor-area metadata, Philadelphia building energy benchmarking where available, NREL ComStock 15-minute load shapes, historical weather, and EPA eGRID carbon intensity.

## Local setup

1. Copy `.env.example` to `.env`.
2. Set `VITE_CESIUM_ION_TOKEN` and `DATABASE_URL`.
3. Install frontend dependencies with `npm install`.
4. Install backend dependencies with `python -m pip install -r backend/requirements.txt`.
5. Seed Tiger with `python scripts/seed_database.py`.
6. Run the backend from `backend/`:

   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

7. In a second terminal, run `npm run dev`.

The current campus inventory contains 50 distinct Temple buildings with authoritative GIS geometry and floor area.
