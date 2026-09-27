# Temple Twin pre-deploy checklist

Use this immediately before creating the Vultr instance.

## Local app

- [ ] Pull latest `main`.
- [ ] Start FastAPI from `backend/`.
- [ ] Start Vite from the repo root.
- [ ] Reality mode loads.
- [ ] Energy mode loads.
- [ ] Search finds SERC.
- [ ] Direct map click opens a building without a camera jump.
- [ ] Timeline crosses midnight without an error flash.
- [ ] Jump several days/weeks.
- [ ] LED toggles on/off.
- [ ] HVAC toggles on/off.
- [ ] Solar toggles on/off.
- [ ] Combined interventions work.
- [ ] Solar panels appear/disappear.
- [ ] Ask Temple Twin answers a campus question.
- [ ] Ask Temple Twin answers a building question.
- [ ] Ask Temple Twin input clears after a successful question.
- [ ] Ask Temple Twin declines clearly unrelated questions.
- [ ] Smaller browser width is usable.

## Secrets

- [ ] `.env` is not tracked.
- [ ] Real Tiger/Snowflake credentials are not in GitHub.
- [ ] Cesium token is appropriately scoped.
- [ ] Production will use `SNOWFLAKE_ROLE=TEMPLE_TWIN_APP`.
- [ ] `ENABLE_DIAGNOSTICS=false` for production.

## Snowflake

- [ ] Run `deploy/snowflake_role.sql` once.
- [ ] Verify Cortex with `TEMPLE_TWIN_APP`.
- [ ] Update local/production env role if the test succeeds.

## Build gate

- [ ] GitHub Actions frontend job passes.
- [ ] GitHub Actions backend pytest job passes.
- [ ] GitHub Actions Docker job passes.

## Assets / submission

- [ ] Final screenshot or GIF ready for README.
- [ ] Demo building/date/time selected.
- [ ] Prepared Ask Temple Twin question selected.
- [ ] 90–120 second demo flow rehearsed.
- [ ] Devpost/OwlHacks copy drafted.

## Values to have copied before Vultr

- [ ] `VITE_CESIUM_ION_TOKEN`
- [ ] `DATABASE_URL`
- [ ] `SNOWFLAKE_ACCOUNT`
- [ ] `SNOWFLAKE_USER`
- [ ] `SNOWFLAKE_PASSWORD`
- [ ] `SNOWFLAKE_WAREHOUSE`
- [ ] `SNOWFLAKE_DATABASE`
- [ ] `SNOWFLAKE_SCHEMA`
- [ ] `SNOWFLAKE_ROLE`
- [ ] intended domain/subdomain
