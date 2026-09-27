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

## Secrets and production environment

- [ ] `.env` is not tracked; repo `.gitignore` includes both `.env` and `.env.*`.
- [ ] Copy `deploy/vultr.env.example` to repo-root `.env` on the server.
- [ ] `docker-compose.yml` keeps `ENABLE_DIAGNOSTICS` defaulted to `false`.
- [ ] `deploy/vultr.env.example` includes every backend runtime environment variable:
  `DATABASE_URL`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`,
  `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_CORTEX_MODEL`,
  and `ENABLE_DIAGNOSTICS`.
- [ ] `VITE_CESIUM_ION_TOKEN` is populated for the frontend build.
- [ ] `DATABASE_URL` includes the Tiger/PostgreSQL SSL requirement used by the account.
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
- [ ] `SNOWFLAKE_CORTEX_MODEL`
- [ ] `ENABLE_DIAGNOSTICS=false`
- [ ] intended domain/subdomain


## Vultr first-start checks

- [ ] Run `./deploy/deploy.sh` from the repository root.
- [ ] Cold-start health check succeeds within the script's 10 attempts.
- [ ] `docker compose ps` shows both services running.
- [ ] `curl -f http://127.0.0.1/health` returns healthy Tiger connectivity.
- [ ] `curl -f http://127.0.0.1/api/simulation` returns simulation metadata.
- [ ] Ask Temple Twin returns a real Cortex answer with diagnostics disabled.
