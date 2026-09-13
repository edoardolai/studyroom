#!/usr/bin/env bash
set -o errexit

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python load_data.py
daphne -b 0.0.0.0 -p "${PORT:-8000}" studyroom.asgi:application
