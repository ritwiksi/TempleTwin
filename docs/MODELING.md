# Temple Twin energy modeling

## Campus data

Temple Twin currently models 50 distinct Main Campus buildings.

For every included building:

- geometry comes from Temple University ArcGIS building services;
- gross/floor area is authoritative source data, not a hand-estimated area;
- Philadelphia 2024 Building Energy Benchmarking is used when an unambiguous building-level annual electricity match exists;
- otherwise annual electricity is calibrated from Temple's FY2025 campus-wide electricity EUI.

The sync pipeline refuses to include a building that lacks an authoritative floor-area input.

## Load-shape model

The temporal load behavior comes from official NREL/OEDI ComStock Philadelphia County files at their native **15-minute resolution**.

For every 15-minute interval the model retains:

- HVAC electricity;
- lighting electricity;
- process/equipment electricity;
- other electricity;
- total demand.

ComStock annual profiles are first scaled so annual energy equals the building's annual target.

## Annual calibration

For a building with reported Philadelphia benchmarking electricity:

`annual_target_kwh = reported_annual_electricity_kwh`

Otherwise:

`annual_target_kwh = Temple_FY2025_campus_electric_EUI × building_floor_area_ft2`

The campus calibration anchor is:

- Temple gross area: 11,122,267 ft²;
- Temple electricity: 612,025 MMBtu/year;
- conversion: 293.071 kWh/MMBtu;
- campus electricity EUI: approximately 16.1 kWh/ft²/year.

## Interactive scenario day

The underlying ComStock profile is annual, but the current interactive API/Tiger/UI exposes one historical Friday:

**September 14, 2018**

That produces **96 states per building**, from 00:00 through 23:45.

Historical Open-Meteo weather is also loaded only for that date. Weather modifies HVAC through the bounded weather-response model, and the same day's irradiance is used for the rooftop-solar scenario.

So the current app is **annual-calibrated but single-day interactive**, not yet a year-round weather/time explorer.

## Energy intensity and color

At each interval:

`energy_intensity_w_ft2 = demand_kw × 1000 / floor_area_ft2`

The frontend derives shared intensity thresholds across the campus profile and applies the same scale to every building.

## Scientific wording

Accurate description:

> Temple Twin uses NREL ComStock 15-minute simulated end-use load shapes for Philadelphia County, scales them to building-level reported electricity where available or Temple's published campus electricity intensity otherwise, and applies historical weather for the interactive scenario day. Building-level interval values are modeled, not Temple smart-meter readings.
