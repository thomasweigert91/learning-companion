# Ticket: Containerisierung und Continuous Integration

## 1. Problem / Ziel

Die Anwendung laeuft bisher ausschliesslich lokal im `.venv` ueber den
Django-Entwicklungsserver. Es gibt weder ein reproduzierbares Artefakt fuer den
Betrieb noch eine automatisierte Pruefung von Pull Requests -- jeder Lauf der
Testsuite haengt daran, dass jemand ihn manuell anstoesst.

Dieses Ticket schliesst beide Luecken:

1. **Container** -- ein Multi-Stage-Dockerfile auf Basis `python:3.12-slim`, das
   die Anwendung unter einem unprivilegierten Benutzer mit `gunicorn` als
   WSGI-Server startet. Ein Entrypoint-Script fuehrt Migrationen und
   `collectstatic` vor dem Start zuverlaessig aus. Eine `docker-compose.yml`
   macht den Container lokal auf Port 8000 startbar.
2. **CI** -- ein GitHub-Actions-Workflow, der bei `push` und `pull_request` auf
   `main` die Abhaengigkeiten installiert (mit Cache), den Django-System-Check
   und einen Linter ausfuehrt und die komplette Testsuite laufen laesst.

**Zwei Voraussetzungen, die der Code heute nicht erfuellt** und die dieses Ticket
deshalb mit abdeckt:

- `settings.py` definiert kein `STATIC_ROOT`. `collectstatic` bricht ohne diese
  Einstellung mit `ImproperlyConfigured` ab -- der Entrypoint waere nicht
  lauffaehig.
- Die SQLite-Datei liegt per `BASE_DIR / "db.sqlite3"` im Anwendungsverzeichnis.
  Dieses Verzeichnis gehoert im Image `root`; ein unprivilegierter Prozess kann
  dort weder die Datenbank anlegen noch die von SQLite benoetigte
  Journal-Datei schreiben. Der Pfad muss ueber die Umgebung auf ein
  beschreibbares Verzeichnis umlenkbar sein.

## 2. Akzeptanzkriterien

### Dockerfile

- [ ] Es existiert ein `Dockerfile` im Projektwurzelverzeichnis mit **mindestens
      zwei Stages** (Build-Stage fuer die Abhaengigkeiten, schlanke
      Runtime-Stage), basierend auf `python:3.12-slim`.
- [ ] Die Runtime-Stage enthaelt **keine** Build-Toolchain (kein `gcc`, kein
      `build-essential`); Compiler werden -- falls ueberhaupt noetig -- nur in
      der Build-Stage installiert.
- [ ] Das Image legt einen unprivilegierten Benutzer an (nicht `root`, UID != 0)
      und setzt `USER` auf diesen Benutzer, **bevor** `CMD`/`ENTRYPOINT` greift.
      `docker run --rm <image> id -u` gibt einen Wert != 0 aus.
- [ ] Der Anwendungsprozess ist `gunicorn` mit
      `learning_companion.wsgi:application`; `gunicorn` steht mit Versionsgrenze
      in `requirements.txt`.
- [ ] Der Container lauscht auf Port 8000 (`EXPOSE 8000`), gebunden an
      `0.0.0.0`.
- [ ] Es sind **keine Secrets** im Image: kein `.env` wird hineinkopiert, kein
      `DJANGO_SECRET_KEY` und kein `OPENAI_API_KEY` steht als `ENV`- oder
      `ARG`-Wert im Dockerfile. `docker history --no-trunc <image>` enthaelt
      keinen Schluesselwert.
- [ ] `PYTHONDONTWRITEBYTECODE=1` und `PYTHONUNBUFFERED=1` sind gesetzt, damit
      keine `.pyc`-Dateien ins Image wandern und Logs ungepuffert erscheinen.

### Entrypoint

- [ ] Es existiert ein `entrypoint.sh`, das in dieser Reihenfolge
      `python manage.py migrate --noinput` und
      `python manage.py collectstatic --noinput` ausfuehrt und anschliessend per
      `exec "$@"` an das `CMD` uebergibt -- damit laeuft `gunicorn` als PID 1
      und empfaengt Signale direkt (sauberes `docker stop`).
- [ ] Das Script beginnt mit `#!/bin/sh` und `set -e`, bricht also beim ersten
      Fehler ab, statt mit halb migrierter Datenbank weiterzustarten.
- [ ] `entrypoint.sh` hat **LF-Zeilenenden** (kein CRLF) und ist im Image
      ausfuehrbar. Eine `.gitattributes`-Regel haelt die Zeilenenden auch auf
      Windows-Checkouts stabil; `file entrypoint.sh` bzw. eine Pruefung auf
      `\r` bleibt ohne Treffer.

### Konfiguration

- [ ] `settings.py` definiert `STATIC_ROOT` (ueber `DJANGO_STATIC_ROOT`
      konfigurierbar, Default `BASE_DIR / "staticfiles"`), sodass
      `collectstatic --noinput` fehlerfrei durchlaeuft.
- [ ] Der SQLite-Pfad ist ueber `DJANGO_DB_PATH` konfigurierbar; der Default
      bleibt `BASE_DIR / "db.sqlite3"`, damit sich die lokale Entwicklung nicht
      aendert. Im Container zeigt die Variable auf ein Verzeichnis, das dem
      unprivilegierten Benutzer gehoert.
- [ ] Statische Dateien werden bei `DEBUG=False` ausgeliefert (WhiteNoise als
      Middleware direkt nach `SecurityMiddleware`); ein Aufruf der
      Admin-Login-Seite im Container liefert CSS mit Status 200 statt 404.
- [ ] `.env.example` dokumentiert die neuen Variablen `DJANGO_DB_PATH` und
      `DJANGO_STATIC_ROOT`.

### .dockerignore

- [ ] Es existiert eine `.dockerignore`, die mindestens `.venv/`, `.git/`,
      `db.sqlite3`, `__pycache__/`, `*.pyc`, `.env`, `staticfiles/` und
      `.workflow/` ausschliesst.
- [ ] Der Build-Context ist dadurch nachweislich klein: der von
      `docker build` gemeldete Transfer-Umfang liegt deutlich unter der Groesse
      des Arbeitsverzeichnisses mit `.venv` und `.git`.

### docker-compose.yml

- [ ] Es existiert eine `docker-compose.yml`, die den Container baut und Port
      8000 des Hosts auf 8000 des Containers mappt.
- [ ] Die Konfiguration liest Umgebungsvariablen aus einer optionalen lokalen
      `.env` (`env_file` mit `required: false`), haelt aber **keine** Secrets im
      Versionsstand.
- [ ] Ein benanntes Volume haelt die SQLite-Datenbank, sodass Daten einen
      `docker compose down`/`up`-Zyklus ueberleben.
- [ ] `docker compose config` validiert die Datei fehlerfrei.

### GitHub Actions CI

- [ ] Es existiert `.github/workflows/ci.yml` mit Triggern auf `push` **und**
      `pull_request` jeweils fuer den Branch `main`.
- [ ] Der Workflow richtet Python 3.12 ein (`actions/setup-python`) und nutzt
      Dependency-Caching (`cache: pip`), damit wiederholte Laeufe die
      Abhaengigkeiten nicht neu herunterladen.
- [ ] Der Workflow installiert die Abhaengigkeiten aus `requirements.txt`.
- [ ] Der Workflow fuehrt aus: einen Linter (`ruff check`), den
      Django-System-Check (`manage.py check`), eine Migrationspruefung
      (`makemigrations --check --dry-run`) und die Testsuite
      (`python manage.py test`).
- [ ] Der Workflow setzt `permissions: contents: read` und pinnt die verwendeten
      Actions auf eine Major-Version, statt `@master` zu referenzieren.
- [ ] Ein zweiter Job baut das Docker-Image (`docker build`), damit ein
      kaputtes Dockerfile die CI rot faerbt.
- [ ] Die CI benoetigt **keine** Secrets: ohne `OPENAI_API_KEY` laeuft die
      Anwendung im Mock-Modus, die Testsuite ist davon unabhaengig.

### Validierung

- [ ] `docker build` laeuft lokal fehlerfrei durch. Docker ist in dieser
      Umgebung verfuegbar (Version 29.7.2), der Build wird also **real
      ausgefuehrt** und nicht nur syntaktisch geprueft.
- [ ] Der gebaute Container startet, fuehrt Migration und `collectstatic` aus
      und beantwortet einen HTTP-Request auf Port 8000 mit einem gueltigen
      Status (200 oder ein Redirect), nicht mit einem Fehler.
- [ ] `ruff check` laeuft ohne Befund ueber den Anwendungscode.
- [ ] Alle 145 bestehenden Tests laufen weiterhin durch
      (`python manage.py test`), insbesondere nach der Aenderung an
      `settings.py`.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Basis-Image `python:3.12-slim` passend zur lokal genutzten Python-Version
  3.12.10; Django 5.2.x, SQLite.
- `gunicorn` und `whitenoise` werden mit Versionsgrenzen in `requirements.txt`
  aufgenommen (Stil der bestehenden Eintraege: `>=x,<y`).
- `ruff` wird als Entwicklungsabhaengigkeit in `requirements-dev.txt` gefuehrt,
  damit das Laufzeit-Image schlank bleibt und der Linter nicht ins Produktions-
  Image wandert.
- Die Aenderungen an `settings.py` bleiben rueckwaertskompatibel: ohne gesetzte
  Umgebungsvariablen verhaelt sich die lokale Entwicklung exakt wie bisher.
- Keine Modell-Aenderungen, keine neuen Migrationen.
- Shell-Script im POSIX-Dialekt (`/bin/sh`), da `slim`-Images keine `bash`
  garantieren.

**Out-of-Scope**

- Kein Wechsel des Datenbank-Backends auf PostgreSQL und kein
  Datenbank-Service in der Compose-Datei.
- Kein Reverse Proxy (nginx, Traefik) und kein TLS-Terminierung.
- Kein Push des Images in eine Registry (GHCR, Docker Hub) und kein
  Multi-Arch-Build.
- Kein Deployment-Workflow, keine Staging- oder Produktionsumgebung.
- Keine Coverage-Messung, kein Test-Matrix-Build ueber mehrere Python-Versionen.
- Kein Health-Check-Endpunkt in der Anwendung und kein `HEALTHCHECK` mit
  Anwendungslogik.
- Kein Container-Security-Scan (Trivy, Snyk) in der CI.
