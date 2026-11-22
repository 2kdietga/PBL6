#!/usr/bin/env bash
set -euo pipefail

# Single-instance demo: finish migrations before accepting requests.
python manage.py migrate --noinput
exec python -u run_services.py
