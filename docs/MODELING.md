# Temple Twin energy modeling — Milestone 3

## Important distinction

Hourly profile **shapes now come from actual NREL ComStock data** downloaded
from the official OEDI public data lake. The prior hand-written occupancy/load
schedule generator has been removed.

Building-level Temple electricity values are still **MODELED ESTIMATES**, not
Temple meter readings.

## Actual ComStock source

Temple Twin uses the official 2021 ComStock AMY2018 county aggregate release:

`2021/comstock_amy2018_release_1`

Geography:

- Pennsylvania
- Philadelphia County
- OEDI county GISJOIN: `g4201010`

The source files are 15-minute aggregate end-use profiles from:

`timeseries_aggregates/by_county/state=PA/`

Configured proxies:

| Temple building | Actual ComStock building-type profile |
|---|---|
| SERC | largeoffice |
| Beury Hall | secondaryschool |
| Engineering Building | mediumoffice |

ComStock does not publish a dedicated research-laboratory building type in this
release. The proxy mapping is therefore a modeling choice, but the underlying
15-minute load values are actual ComStock outputs rather than invented curves.

## End-use decomposition from source data

The loader groups actual ComStock electricity end uses into:

- HVAC: cooling, fans, heat recovery, heat rejection, electric heating, pumps
- Lighting: interior + exterior lighting
- Process: interior equipment + refrigeration
- Other: remaining electricity needed to reconcile with total electricity

ComStock publishes timeseries energy values in kWh at 15-minute intervals.
Temple Twin sums four intervals to an hourly kWh value; for a one-hour interval
that is numerically equal to average kW.

The source timestamp marks the end of the 15-minute interval, which the loader
handles when assigning samples to hours.

## Friday extraction

The representative day is Friday, September 14, 2018 from the AMY2018 ComStock
release. The backend returns exactly 24 ordered rows, 00:00–23:00.

No synthetic Friday schedule is generated.

## Temple calibration

The public Temple campus anchor remains:

- gross area: 11,122,267 ft²
- electricity: 612,025 MMBtu/year
- electricity-only campus EUI: about 16.1 kWh/ft²/year

SERC's approximately 250,000 ft² area is publicly documented. Beury and
Engineering floor areas remain explicit estimates until a better authoritative
source is located.

The selected ComStock profile supplies the **shape and component proportions**.
A single scalar then scales the full annual ComStock electricity profile to the
building's modeled annual target:

`annual_target_kwh = modeled_eui_kwh_ft2 × floor_area_ft2`

The current Temple-specific annual EUI values remain model assumptions:

- SERC: 28.0 kWh/ft²/year
- Beury: 23.0 kWh/ft²/year
- Engineering: 17.5 kWh/ft²/year

So: hourly behavior is ComStock-derived; absolute Temple magnitude is modeled.

## Scientific honesty

Do not describe these profiles as Temple meter readings.

A precise description is:

> "Hourly load shapes and end-use composition are derived from NREL ComStock
> Philadelphia County simulations and scaled to Temple-specific modeled annual
> electricity targets."

ComStock itself is a validated simulation dataset, not measured building meter
data.
