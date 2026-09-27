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

Historical Open-Meteo weather is cached for the same 91-day window. The ComStock 2018 profile already contains weather-responsive HVAC behavior, so Temple Twin does not apply an additional arbitrary temperature multiplier. Open-Meteo irradiance drives the rooftop-solar scenario and weather is shown as explanatory context.

The frontend exposes one continuous master timeline but fetches the active calendar day from the API on demand. This keeps browser payloads manageable while the full three-month state history remains stored in Tiger.

## Energy intensity and color

At each interval:

`energy_intensity_w_ft2 = demand_kw × 1000 / building_floor_area_ft2`

The frontend derives shared intensity thresholds from the active day's campus profile and applies the same scale to every building for that day.

## Intervention scenarios

### LED code-upgrade retrofit

Temple Twin does not claim to know the installed fixture inventory in each building. Instead it uses a transparent code-to-code scenario based on ASHRAE Building Area Method lighting power density (LPD).

For the closest building category:

`lighting_reduction = 1 - (LPD_2019_target / LPD_2004_reference)`

and for every 15-minute interval:

`lighting_kw_new = lighting_kw_baseline × (1 - lighting_reduction)`

Examples of the source values used by the model include school/university 1.20 → 0.70 W/ft² and office 1.00 → 0.62 W/ft². The model labels these as reference/target values rather than measured Temple LPDs.

### HVAC controls optimization

The HVAC scenario represents a controls measure, not an equipment replacement with an invented COP. PNNL/DOE found about 6% whole-building savings from limiting heating/cooling to periods when a commercial building is most likely occupied.

For each active day:

`target_savings_kwh = 0.06 × baseline_building_kwh`

`hvac_reduction_fraction = min(1, target_savings_kwh / baseline_hvac_kwh)`

`hvac_kw_new = hvac_kw_baseline × (1 - hvac_reduction_fraction)`

This translates the published whole-building benchmark through each building/day's actual modeled HVAC share. If HVAC energy is insufficient to achieve the full target, savings are limited to available HVAC energy.

### Rooftop solar

Solar leaves underlying building demand unchanged.

`pv_capacity_kw = roof_area_ft² × 0.092903 × 0.60 × 0.160`

`solar_kw = pv_capacity_kw × (GHI / 1000) × (1 - 0.14)`

`grid_import_kw = max(building_demand_kw - solar_kw, 0)`

The 60% usable-roof fraction is a simplified commercial-roof suitability assumption; 160 W/m² comes from NREL rooftop technical-potential work; 14% is the PVWatts default system-loss assumption.

Intervention savings shown in the detail panel are day-specific. Temple Twin does not extrapolate one day's retrofit savings into an annual scenario total.

## Scientific wording

Accurate description:

> Temple Twin uses NREL ComStock 15-minute simulated end-use load shapes for Philadelphia County, scales the annual profile to building-level reported electricity where available or Temple's published campus electricity intensity otherwise, and applies historical weather across a continuous three-month simulation window. Building-level interval values are modeled, not Temple smart-meter readings.
