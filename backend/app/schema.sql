CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS buildings (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    floor_area_ft2 DOUBLE PRECISION NOT NULL CHECK (floor_area_ft2 > 0),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    approx_height_m DOUBLE PRECISION NOT NULL,
    building_type TEXT NOT NULL,
    area_source TEXT NOT NULL,
    area_is_estimated BOOLEAN NOT NULL,
    modeled_annual_eui_kwh_ft2 DOUBLE PRECISION NOT NULL,
    model_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_hourly (
    timestamp TIMESTAMPTZ NOT NULL,
    temperature_f DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    ghi_w_m2 DOUBLE PRECISION,
    dni_w_m2 DOUBLE PRECISION,
    weather_code INTEGER,
    source TEXT
) WITH (
    tsdb.hypertable,
    tsdb.partition_column='timestamp'
);

CREATE TABLE IF NOT EXISTS building_hourly_state (
    timestamp TIMESTAMPTZ NOT NULL,
    building_id BIGINT NOT NULL REFERENCES buildings(id),
    scenario_id TEXT NOT NULL,
    hvac_kw DOUBLE PRECISION NOT NULL CHECK (hvac_kw >= 0),
    lighting_kw DOUBLE PRECISION NOT NULL CHECK (lighting_kw >= 0),
    process_kw DOUBLE PRECISION NOT NULL CHECK (process_kw >= 0),
    other_kw DOUBLE PRECISION NOT NULL CHECK (other_kw >= 0),
    demand_kw DOUBLE PRECISION NOT NULL CHECK (demand_kw >= 0),
    solar_kw DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (solar_kw >= 0),
    grid_import_kw DOUBLE PRECISION NOT NULL CHECK (grid_import_kw >= 0),
    energy_intensity_w_ft2 DOUBLE PRECISION NOT NULL CHECK (energy_intensity_w_ft2 >= 0),
    carbon_kg DOUBLE PRECISION,
    PRIMARY KEY (building_id, scenario_id, timestamp)
) WITH (
    tsdb.hypertable,
    tsdb.partition_column='timestamp'
);

CREATE INDEX IF NOT EXISTS idx_building_hourly_building_timestamp
    ON building_hourly_state (building_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_building_hourly_scenario_timestamp
    ON building_hourly_state (scenario_id, timestamp DESC);
