# Docker Compose execution environment

The default Compose stack starts PostgreSQL, initializes its schema, and starts the local web dashboard. The
main trading bot is in the explicit `live` profile. Compose does not install
cron, systemd timers, widget machines, or episode machines.

## Setup

1. Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` with a unique,
   URL-safe password. Keep `.env` private. The password is used for both the
   PostgreSQL service and `DATABASE_URL` inside the Python services.
2. Run `mkdir -p logs` as your normal host user. Place the existing runtime
   data and models under `data/`, including `data/config_prod.json` for the
   Python services. For live bot use, also provide the required credentials in
   `.env` and the reviewed, target-date PREOPEN runtime env in
   `data/threshold_cycle/runtime_env/`. These are mounted from the host rather
   than copied into the image.
3. Run `docker compose config -q` to validate interpolation, then
   `docker compose up -d --build db schema web`. Open `http://127.0.0.1:5000` (or the
   configured `WEB_PORT`). `docker compose logs -f web` shows startup errors.

The dashboard binds to localhost. PostgreSQL is reachable only on the Compose
network. The host `data/` and `logs/` folders are bind-mounted, while the DB
uses the `postgres_data` named volume. The schema service runs the existing
`DBManager.init_db()` against that volume before web or bot starts. The Python
services select the installed `psycopg2` driver explicitly and use a writable
Numba cache under `/tmp`. The image runs as UID/GID `1000:1000`,
so those host folders must be writable by that identity. Create `logs/`
before Compose starts so Docker does not create a root-owned bind source.

## Live bot

The live profile mounts `.git` read-only for source provenance and launches the existing `src/run_bot.sh` supervisor, which can
submit real broker orders. Follow the current Plan Rebase, daily checklist,
and runbook approval and PREOPEN handoff before explicitly running:

```bash
docker compose --profile live up -d bot
```

Do not run a host systemd/tmux bot against the same account and state at the
same time. `docker compose stop bot` stops the container; it does not change
broker state or replace the normal shutdown and custody checks. Starting the
profile does not install the repository's separate cron and systemd services.

`DATABASE_URL` in Compose targets the new PostgreSQL volume. It starts empty;
the stack does not migrate an existing host database automatically. Back up or
restore data explicitly before using an existing trading account. The image
uses Python 3.12 because the available `pandas-ta` release requires it.
It installs the repository's `requirements.txt` with container-only bounds
`pandas>=2.3.2,<3` and `pandas-ta==0.4.71b0`, plus `python-dotenv` and
`gunicorn` for the bot and web entry points.
