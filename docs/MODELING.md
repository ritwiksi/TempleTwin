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

Temporal load behavior comes from official NREL/OEDI ComStock Philadelphia County files at their native **15-minute resolution**.

For every interval the model retains:

- HVAC electricity;
- lighting electricity;
- process/equipment electricity;
- other electricity;
- total demand.

The full annual ComStock profile is scaled so its annual energy equals the building's annual target. This preserves ComStock's weekday/weekend and seasonal variation instead of creating an average day.

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

## Interactive simulation window

The interactive simulation currently spans:

**September 1, 2018 through November 30, 2018**

That is 91 consecutive days and **8,736 15-minute states per building**.

Historical Open-Meteo weather is cached for the same 91-day window. Temperature modifies HVAC through the bounded weather-response model, and historical irradiance drives the rooftop-solar scenario.

The frontend exposes one continuous master timeline but fetches the active calendar day from the API on demand. This keeps browser payloads manageable while the full three-month state history remains stored in Tiger.

## Energy intensity and color

At each interval:

`energy_intensity_w_ft2 = demand_kw × 1000 / building_floor_area_ft2`

The frontend derives shared intensity thresholds from the active day's campus profile and applies the same scale to every building for that day.

## Intervention scenarios

- LED retrofit reduces lighting load only.
- HVAC efficiency reduces HVAC load only.
- Rooftop solar leaves building demand unchanged and reduces grid import using historical irradiance.

Intervention savings shown in the detail panel are day-specific. Temple Twin does not extrapolate one day's retrofit savings into an annual scenario total.

## Scientific wording

Accurate description:

> Temple Twin uses NREL ComStock 15-minute simulated end-use load shapes for Philadelphia County, scales the annual profile to building-level reported electricity where available or Temple's published campus electricity intensity otherwise, and applies historical weather across a continuous three-month simulation window. Building-level interval values are modeled, not Temple smart-meter readings.
