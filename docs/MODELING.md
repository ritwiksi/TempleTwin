# Temple Twin energy modeling

## Current data path

The temporal load behavior is taken from official NREL/OEDI ComStock
Philadelphia County files at their native **15-minute resolution**. Temple Twin
does not generate synthetic day/night schedules.

For every 15-minute interval the model retains:

- HVAC electricity
- lighting electricity
- process/equipment electricity
- other electricity
- total demand

The Friday API/UI therefore uses **96 states per building**, from 00:00 through
23:45.

## Absolute magnitude calibration

The earlier hand-picked building EUIs (28 / 23 / 17.5 kWh/ft²/year) have been
removed.

Until building-specific annual Temple electricity data or a separately
calibrated physics model is available, all three buildings use the same public
Temple campus-wide electricity-only calibration anchor:

- Temple gross area: 11,122,267 ft²
- Temple electricity: 612,025 MMBtu/year
- conversion: 293.071 kWh/MMBtu
- campus electricity EUI: approximately 16.1 kWh/ft²/year

For each building:

`annual_target_kwh = campus_electric_eui × building_floor_area_ft2`

This intentionally does **not** invent a higher annual EUI for a lab building.
Different 15-minute behavior still comes from the selected ComStock temporal
profile, but the annual magnitude is neutral until stronger building-specific
evidence is available.

## Building area status

- SERC: approximately 250,000 ft² from Temple public documentation.
- Beury Hall: area remains explicitly estimated.
- Engineering Building: area remains explicitly estimated.

Those estimates remain the largest non-public inputs in the magnitude
calculation and must not be described as measured floor areas.

## Color thresholds

The prior fixed hand-picked thresholds were removed. The frontend computes one
shared set of quartile breaks from all three buildings' 96 Friday intensity
values. Every building at every timestamp is compared against the same breaks.

This is a visualization classification, not an energy measurement.

## Scientific wording

Accurate description:

> Temple Twin uses NREL ComStock 15-minute simulated end-use load shapes for
> Philadelphia County and scales them to Temple's published campus-wide
> electricity intensity. Building-level values are modeled estimates, not
> Temple meter readings.

## Alternatives under evaluation

ComStock is not the only option.

- Building Data Genome 2 provides real measured hourly whole-building meter
  data across more than 1,600 non-residential buildings. It is attractive for
  empirical load-shape validation, but buildings are anonymized and it lacks
  ComStock-style 15-minute end-use decomposition.
- DOE/PNNL Commercial Prototype Buildings and EnergyPlus provide physics-based
  whole-building simulation models. A custom EnergyPlus model could ultimately
  represent laboratory ventilation/process loads more explicitly, but it would
  require substantial building-specific geometry, schedules, systems, and
  calibration inputs.
- LBNL CityBES/CBES also uses physics-based building-energy simulation for
  building/city-scale analysis and is another possible future validation route.

The current application keeps its building-type mapping internal while this
modeling choice is evaluated.
