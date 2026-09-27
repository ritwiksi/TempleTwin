# Temple Twin

Temple Twin is a 3D campus energy digital twin for Temple University's Main Campus. It combines real campus geometry and floor-area metadata with calibrated building-energy models so users can explore how campus electricity demand changes over time, compare buildings, simulate decarbonization interventions, and ask grounded questions about the model.

> **Important:** Temple Twin does not use live Temple smart-meter data. Building interval values are modeled estimates.

## What it does

- Visualizes 50 Temple University buildings in an interactive Cesium 3D campus.
- Replays 15-minute electricity demand across a continuous three-month simulation window.
- Breaks modeled load into HVAC, lighting, process/equipment, and other electricity.
- Estimates grid-electricity carbon using EPA eGRID.
- Simulates LED retrofits, HVAC efficiency improvements, and rooftop solar.
- Uses historical weather and irradiance for the modeled simulation period.
- Provides **Ask Temple Twin**, a Snowflake Cortex-powered explanation layer grounded in the active campus/building context.

## Architecture

```text
Temple GIS + Philadelphia Benchmarking + NREL ComStock
                    |
                    v
          Python modeling / ETL
                    |
                    v
              Tiger Data
                    |
                    v
              FastAPI API
              /        \
             /          \
      React/Cesium   Snowflake Cortex
          UI          Ask Temple Twin
```

Production traffic is served through nginx. The browser calls same-origin `/api/*` routes, which nginx forwards to FastAPI on the private Docker network.

## Energy modeling

### Building geometry and floor area

Temple Twin uses Temple University public GIS data for building identity, footprint geometry, location, and floor-area attributes.

### Annual electricity calibration

When an unambiguous building-level match exists in Philadelphia's 2024 Building Energy Benchmarking data, that reported annual electricity value is used as the building's annual calibration target.

Otherwise:

```text
annual_target_kwh = Temple FY2025 campus electricity EUI × floor area
```

### 15-minute load profiles

Temporal load behavior comes from NREL/OEDI ComStock Philadelphia County end-use profiles at 15-minute resolution.

Each interval retains:

- HVAC
- lighting
- process/equipment
- other electricity
- total demand

The annual ComStock profile is scaled to the building's annual electricity target. This preserves modeled weekday/weekend and seasonal variation while matching the annual calibration.

The interactive simulation currently covers **September 1 through November 30, 2018**, or 8,736 15-minute states per building.

See [docs/MODELING.md](docs/MODELING.md) for the full methodology.

## Interventions

### LED retrofit

Reduces modeled lighting load only.

### HVAC efficiency

Reduces modeled HVAC load only.

### Rooftop solar

Uses estimated usable roof area and historical irradiance to estimate PV generation. Solar reduces grid import rather than changing the building's underlying electricity demand.

Intervention results are modeled scenarios, not measured savings.

## Ask Temple Twin

Ask Temple Twin sends a compact, structured snapshot of the currently selected building—or the campus when no building is selected—to Snowflake Cortex.

Questions can cover topics such as:

- current building or campus demand;
- end-use drivers;
- intervention effects;
- rooftop solar;
- weather;
- carbon;
- model assumptions and limitations;
- data sources and calibration.

The prompt explicitly instructs Cortex not to invent live meter readings, occupancy, equipment conditions, or unsupported causes.

## Data sources

- **Temple University GIS** — building footprints, identities, locations, and floor area.
- **City of Philadelphia Building Energy Benchmarking** — reported annual electricity where an unambiguous building-level match exists.
- **NREL / OEDI ComStock** — Philadelphia County simulated 15-minute end-use load profiles.
- **Open-Meteo Historical Archive** — historical weather and irradiance.
- **EPA eGRID** — grid carbon intensity.
- **Tiger Data / PostgreSQL** — persistent building, weather, and profile data.
- **Snowflake Cortex** — grounded natural-language explanations through Ask Temple Twin.

See [docs/SOURCES.md](docs/SOURCES.md) for source details.

## Tech stack

**Frontend**

- React 19
- TypeScript
- Vite
- Cesium / Google Photorealistic 3D Tiles

**Backend**

- FastAPI
- Python 3.12
- psycopg
- Tiger Data / PostgreSQL
- Snowflake Python Connector
- Snowflake Cortex

**Infrastructure**

- Docker / Docker Compose
- nginx
- GitHub Actions
- Vultr deployment configuration

## Local setup

1. Clone the repository.

   ```bash
   git clone https://github.com/ritwiksi/TempleTwin.git
   cd TempleTwin
   ```

2. Copy the environment template.

   ```bash
   cp .env.example .env
   ```

3. Fill in the required Tiger, Cesium, and Snowflake values.

4. Install frontend dependencies.

   ```bash
   npm install
   ```

5. Install backend dependencies.

   ```bash
   python -m pip install -r backend/requirements.txt
   ```

6. Seed Tiger if needed.

   ```bash
   python scripts/seed_database.py
   ```

7. Start the backend from `backend/`.

   ```bash
   cd backend
   python -m uvicorn app.main:app --reload --port 8000
   ```

8. In another terminal, start the frontend from the repository root.

   ```bash
   npm run dev
   ```

## Testing

Frontend build:

```bash
npm run build
```

Backend tests:

```bash
pytest -q backend/tests
```

Docker validation is also run in GitHub Actions on pushes and pull requests.

## Production deployment

The repository includes:

- `Dockerfile.backend`
- `Dockerfile.frontend`
- `docker-compose.yml`
- `deploy/nginx.conf`
- `deploy/deploy.sh`
- `deploy/vultr.env.example`
- `deploy/snowflake_role.sql`

Follow [deploy/README.md](deploy/README.md) for the Vultr, domain, HTTPS, Snowflake-role, and production smoke-test procedure.

## Limitations

- Interval values are modeled estimates, not Temple smart-meter readings.
- Only buildings with authoritative GIS floor-area data are included.
- Building-level annual electricity is reported only where an unambiguous Philadelphia benchmarking match exists; otherwise it is campus-EUI calibrated.
- Intervention savings are scenario assumptions rather than engineering-grade retrofit projections.
- Rooftop solar uses simplified usable-roof and PV performance assumptions.
- Historical weather supports the selected simulation period; Temple Twin is not a live weather or building-operations system.

## Sponsor / platform usage

Temple Twin explicitly uses:

- **Snowflake Cortex** for Ask Temple Twin;
- **Tiger Data** for the application database;
- **Vultr** for production hosting;
- **Cesium ion / Google Photorealistic 3D Tiles** for the 3D campus experience.

## License

MIT
