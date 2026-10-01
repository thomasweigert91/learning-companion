#!/bin/sh
# Startet die Anwendung erst, wenn Schema und statische Dateien stehen.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# exec statt Aufruf: gunicorn wird PID 1 und bekommt das SIGTERM aus
# "docker stop" direkt -- sonst schluckt es die Shell und der Container
# laeuft in den Timeout.
exec "$@"
