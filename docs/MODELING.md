# Temple Twin energy modeling — Milestone 3

## Status

All building-level electricity values are **MODELED ESTIMATES**, not Temple
University meter readings.

## Primary source basis

- Temple University FY2025 Sustainability Action Plan/public sustainability data:
  campus gross area = 11,122,267 ft²; campus electricity = 612,025 MMBtu.
- Conversion used by the project: 293.071 kWh/MMBtu.
- Resulting campus-wide electricity-only calibration anchor: approximately
  16.1 kWh/ft²/year.
- Temple public documentation describes SERC as approximately 250,000 ft² and
  as an education/interdisciplinary research facility with teaching and
  research laboratories.
- DOE/NREL ComStock is the intended load-shape source. NREL documents individual
  and aggregate commercial-building timeseries at 15-minute resolution with
  separate end-use categories.

The campus 16.1 kWh/ft²/year figure is **not** assigned to every building.

## Building table and floor area provenance

The authoritative/estimated status is stored in
`backend/app/data/buildings.csv`.

- **SERC:** 250,000 ft², verified from Temple public documentation.
- **Beury Hall:** estimated for this hackathon model from an approximately
  38,800 ft² map footprint × 3 floors = 116,400 ft². This must be replaced if
  an authoritative gross-area source is found.
- **Engineering Building:** estimated from an approximately 33,550 ft² map
  footprint × 9 floors = ~302,000 ft². Temple's current directory includes
  Engineering offices in room 907, which supports the nine-floor assumption.
  The gross area remains explicitly marked estimated.

## Annual magnitude calibration

The model uses configurable electricity-only EUIs:

| Building | Modeled EUI (kWh/ft²/year) | Rationale |
|---|---:|---|
| SERC | 28.0 | research-lab dominant; highest ventilation/process intensity |
| Beury | 23.0 | mixed lab/classroom/office; elevated process base |
| Engineering | 17.5 | academic engineering/labs/offices; closer to campus anchor |

These are assumptions, not measured values.

For each building:

`annual_target_kwh = modeled_annual_electric_eui_kwh_ft2 × floor_area_ft2`

The annual target is decomposed into HVAC, lighting, process, and other
components. Each component's 8760-hour shape is independently normalized and
scaled to its component annual target. Therefore the final annual profile sums
exactly to the building annual target (within floating-point tolerance).

## ComStock processing

`scripts/prepare_comstock.py` is the ingestion utility for a downloaded/exported
NREL ComStock timeseries. It:

1. reads subhourly end-use values;
2. clamps negative input values to zero;
3. aggregates 15-minute average kW values to hourly mean kW;
4. retains HVAC, lighting, process, and other separately;
5. emits normalized hourly end-use shapes.

NREL's public raw dataset is very large and is hosted in OEDI. The current repo
does **not** claim that its compact checked-in representative schedule fixture
is a raw ComStock export. The fixture exists so the pipeline and calibration can
be implemented/tested without committing enormous source files. Before a final
scientific presentation, a selected ComStock archetype export can be passed
through the same processor without changing the model API.

## Representative Friday

Milestone 3 uses Friday, September 18, 2026 and outputs exactly 24 records,
00:00–23:00. The representative schedules intentionally differ:

- SERC retains the strongest nighttime process/lab base load.
- Beury retains a substantial lab base but has more daytime modulation.
- Engineering has the smallest nighttime process base and a stronger
  daytime academic schedule.

Weather correction is **not** included here; that belongs to Milestone 6.

## End-use decomposition

Every hourly state contains:

- `hvac_kw`
- `lighting_kw`
- `process_kw`
- `other_kw`
- `demand_kw`

and enforces:

`demand_kw = hvac_kw + lighting_kw + process_kw + other_kw`

This separation is required so later LED and HVAC interventions affect only
their appropriate components.

## Traceability

All numerical assumptions live in
`backend/app/config/model_parameters.py`, and area provenance/confidence lives
in `backend/app/data/buildings.csv`. Tuning constants are not scattered through
application code.
