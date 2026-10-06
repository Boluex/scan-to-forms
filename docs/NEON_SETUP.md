# Neon PostgreSQL Free setup

Part of the **ZERO-BUDGET / FREE-TIER CONTROLLED BETA**. No provider connection has been tested with real credentials. PostgreSQL is the authoritative store for users, orders, payment records, OCR jobs and reviewed results; Redis is not.

## Create and copy the connection

1. Create/sign in to a [Neon account](https://console.neon.tech), select the **Free** plan, and create a project for this beta. Choose a region near the Render backend where available. Do not select Launch/Scale or an upgrade.
2. In the project's database controls, create a database such as `scanforms_beta`, or deliberately use the default `neondb`. Select the intended branch and a database role with permission to run Django migrations.
3. Open **Connect**, select that branch/database/role and turn **Connection pooling OFF**. Copy the PostgreSQL connection URI only, without a `psql` command or shell quotes.
4. Use the **direct hostname**, without `-pooler`, for both the API and worker. The existing processing/retry code holds PostgreSQL session advisory locks. Neon's transaction pool cannot preserve those session locks. The configuration rejects Neon pooler URLs. See [Neon pooling](https://neon.com/docs/connect/connection-pooling) ([official documentation source](https://github.com/neondatabase/website/blob/main/content/docs/connect/connection-pooling.md)).
5. Keep TLS enabled. The URI has this shape (illustrative only):

   ```text
   postgresql://ROLE:PASSWORD@DIRECT_HOST/DATABASE?sslmode=require&channel_binding=require
   ```

   The app upgrades `sslmode=require` to **`verify-full`**, using the system CA bundle, and preserves `channel_binding=require` when supplied. This validates the server certificate and hostname. `disable`, `allow` and `prefer` are rejected for Neon/external beta connections. For a custom trusted CA bundle, set `DATABASE_SSL_ROOT_CERT` to its absolute path on the machine/container; normally leave it unset. Do not remove TLS to fix a connection error. See [Neon secure connections](https://neon.com/docs/connect/connect-securely).
6. Copy the **same URI** into Render backend **Environment → `DATABASE_URL`** and Ubuntu's ignored **`.env.worker` → `DATABASE_URL`**. Set `EXTERNAL_SERVICES_REQUIRED=true` on both. If separate credentials are used later, they must resolve to the same direct endpoint, branch and database with the required privileges. No URL goes into the frontend.
7. Never commit the URI, print environment dumps, or paste credentials into chat. Rotate an exposed database password and update both services.

## Migrations and connectivity

Complete Upstash and R2 setup before running the full external settings: the beta deliberately fails startup if those required values are absent. Set up `.env.worker` using [the worker guide](REMOTE_OCR_WORKER.md). From the repository root, with the backend Python dependencies installed:

```bash
export SCANTO_FORMS_ENV_FILE="$PWD/.env.worker"
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py migrate --noinput
.venv/bin/python backend/manage.py showmigrations --plan
.venv/bin/python backend/manage.py shell -c 'from django.db import connection; c = connection.cursor(); c.execute("SELECT 1"); assert c.fetchone()[0] == 1; c.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"); assert c.fetchone()[0]; print("PostgreSQL query and TLS passed")'
```

Use your worker virtualenv path if different. `check` alone does **not** test connectivity. The last command connects to the selected database and checks server-side TLS without printing the URI. Run only after inserting your real credentials; it has not been run against Neon here.

The Render API's `scripts/start-web.sh` also runs existing migrations on startup (`RUN_MIGRATIONS=true`, one API instance). Do not run local and Render migrations concurrently. No model changes or special Neon migrations are required. Start the matching worker revision only after API migrations succeed.

To create your operator, use the same environment and run:

```bash
.venv/bin/python backend/manage.py createsuperuser
```

Free Render services do not provide an interactive shell; this command runs locally against Neon. No Render database access list is involved.

## Limits and operation

As checked September 28, 2026, Neon Free includes **100 CU-hours per project**, **0.5 GB database storage per project**, and **5 GB public network transfer per project**. Compute scales to zero after inactivity. Review the [current plans](https://neon.com/docs/introduction/plans) ([official source](https://github.com/neondatabase/website/blob/main/content/docs/introduction/plans.md)) and your console's quota period before starting.

These are usage allowances, not a promise of permanent free capacity. Inspect usage regularly and pause beta work before limits are exhausted; do not upgrade automatically. Frequent database-backed health checks and active worker/database traffic can keep compute awake. Cold connections may take longer after suspension. Keep copies of originals and take database exports appropriate to this small beta; a short restore window is not a backup policy.
