#!/usr/bin/env bash
set -euo pipefail

# Apply migrations in the web deployment before starting this process.
python manage.py migrate --check
exec python manage.py mqtt_worker
