# syntax=docker/dockerfile:1

# --- Stage 1: Abhaengigkeiten als Wheels bauen -------------------------------
# Alles, was zum Bauen noetig ist (pip-Cache, Quell-Archive, ggf. Compiler),
# bleibt in dieser Stage zurueck. In die Runtime wandern nur die Wheels.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt


# --- Stage 2: schlanke Laufzeit ----------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_STATIC_ROOT=/app/staticfiles

# Unprivilegierter Benutzer. Kein Home-Verzeichnis, keine Login-Shell -- der
# Prozess braucht beides nicht.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app

# Installation aus den vorgebauten Wheels, ohne Netzwerkzugriff (--no-index).
COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.txt \
 && rm -rf /wheels /tmp/requirements.txt

WORKDIR /app

COPY --chown=app:app manage.py ./
COPY --chown=app:app learning_companion/ ./learning_companion/
COPY --chown=app:app core/ ./core/

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# /data haelt die SQLite-Datei, /app/staticfiles das Ergebnis von collectstatic.
# Beide muessen dem unprivilegierten Benutzer gehoeren: SQLite legt neben der
# Datenbank eine Journal-Datei an und braucht dafuer Schreibrechte auf das
# Verzeichnis selbst.
RUN mkdir -p /data /app/staticfiles \
 && chown -R app:app /data /app/staticfiles

USER app

EXPOSE 8000

ENTRYPOINT ["entrypoint.sh"]
CMD ["gunicorn", "learning_companion.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-"]
