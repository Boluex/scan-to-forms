#!/bin/sh
set -eu
# Single API instance for controlled beta. Paid multi-instance deployments should
# run migrations once in a pre-deploy step and set RUN_MIGRATIONS=false.
if [ "${RUN_MIGRATIONS:-true}" = true ]; then
  python manage.py migrate --noinput
fi
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}" --timeout 120 --access-logfile -
