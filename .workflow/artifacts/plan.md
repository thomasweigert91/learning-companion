# Implementierungs-Plan: Containerisierung und Continuous Integration

## 1. Betroffene Dateien

- Neu: `Dockerfile`
- Neu: `.dockerignore`
- Neu: `entrypoint.sh`
- Neu: `docker-compose.yml`
- Neu: `.github/workflows/ci.yml`
- Neu: `requirements-dev.txt`
- Neu: `pyproject.toml` (nur `[tool.ruff]`-Konfiguration)
- Ändern: `requirements.txt` (`gunicorn`, `whitenoise`)
- Ändern: `learning_companion/settings.py` (`STATIC_ROOT`, `DJANGO_DB_PATH`, WhiteNoise)
- Ändern: `.env.example` (neue Variablen dokumentieren)
- Ändern: `.gitattributes` (LF für `entrypoint.sh` erzwingen)

## 2. Datenmodelle & Migrationen

**Keine.** Das Feature ist reine Infrastruktur: kein Modell, kein Feld, keine
Migration. `python manage.py makemigrations --check --dry-run` muss unverändert
"No changes detected" melden -- die CI prüft das künftig bei jedem Lauf.

Die einzigen Änderungen an `settings.py` betreffen Konfiguration, nicht Schema:

| Einstellung | Heute | Künftig | Rückwärtskompatibel? |
|---|---|---|---|
| `STATIC_ROOT` | nicht gesetzt → `collectstatic` bricht ab | `os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")` | ja, neu und additiv |
| `DATABASES.default.NAME` | fest `BASE_DIR / "db.sqlite3"` | `os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3")` | ja, Default identisch |
| `MIDDLEWARE` | ohne WhiteNoise | WhiteNoise direkt nach `SecurityMiddleware` | ja, bei `DEBUG=True` unauffällig |

`staticfiles/` ist in `.gitignore` bereits als `/staticfiles/` ausgeschlossen --
der `collectstatic`-Output landet also nicht im Versionsstand.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Abhängigkeiten und Settings** --
      `requirements.txt` um `gunicorn>=23.0,<24.0` und `whitenoise>=6.7,<7.0`
      ergänzen (Stil der Bestandszeilen: `>=x,<y`). Neu: `requirements-dev.txt`
      mit `-r requirements.txt` und `ruff>=0.6,<1.0` -- der Linter bleibt damit
      aus dem Laufzeit-Image heraus.

      In `settings.py`:
      ```python
      DATABASES = {
          "default": {
              "ENGINE": "django.db.backends.sqlite3",
              "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
          }
      }

      STATIC_URL = "static/"
      STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")
      STORAGES = {
          "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
          "staticfiles": {
              "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
          },
      }
      ```
      WhiteNoise als `"whitenoise.middleware.WhiteNoiseMiddleware"` direkt nach
      `SecurityMiddleware` einhängen -- die von WhiteNoise dokumentierte
      Position.

      `pyproject.toml` mit einer minimalen `[tool.ruff]`-Sektion anlegen
      (`line-length = 100`, Migrations und `.venv` ausgeschlossen), damit lokal
      und in der CI derselbe Regelsatz greift.

- [ ] **Schritt 2: Dockerfile (Multi-Stage)** --

      *Stage `builder`* auf `python:3.12-slim`: `requirements.txt` kopieren und
      `pip wheel --wheel-dir /wheels -r requirements.txt` ausführen. Die Wheels
      sind das einzige, was in die Runtime-Stage übernommen wird -- pip-Cache,
      Quell-Archive und eine eventuelle Toolchain bleiben zurück.

      *Stage `runtime`* auf `python:3.12-slim`:
      - `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`
      - Benutzer anlegen: `groupadd --system --gid 1000 app` +
        `useradd --system --uid 1000 --gid app --no-create-home app`
      - `--from=builder /wheels` kopieren, daraus
        `pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt`,
        danach `rm -rf /wheels`
      - Anwendungscode nach `/app` kopieren, `entrypoint.sh` nach
        `/usr/local/bin/entrypoint.sh` mit `chmod +x`
      - `/data` als Verzeichnis für die SQLite-Datei anlegen und zusammen mit
        `/app/staticfiles` an `app:app` übereignen -- **das** ist der Punkt, an
        dem ein unprivilegierter Prozess sonst scheitert: SQLite braucht
        Schreibrechte nicht nur auf die Datei, sondern auf das *Verzeichnis*
        (Journal- bzw. WAL-Datei).
      - `ENV DJANGO_DB_PATH=/data/db.sqlite3 DJANGO_STATIC_ROOT=/app/staticfiles`
        -- Pfade, keine Secrets.
      - `USER app`, `EXPOSE 8000`,
        `ENTRYPOINT ["entrypoint.sh"]`,
        `CMD ["gunicorn", "learning_companion.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]`

      Bewusst **nicht** im Image: `.env`, `SECRET_KEY`, `OPENAI_API_KEY`. Die
      `.dockerignore` schließt `.env` zusätzlich aus, damit auch ein
      versehentliches `COPY . .` den Schlüssel nicht einzieht.

- [ ] **Schritt 3: entrypoint.sh** --
      ```sh
      #!/bin/sh
      set -e
      python manage.py migrate --noinput
      python manage.py collectstatic --noinput
      exec "$@"
      ```
      `set -e` verhindert einen Start mit halb migrierter Datenbank. `exec`
      ersetzt die Shell durch gunicorn, sodass gunicorn PID 1 wird und `SIGTERM`
      aus `docker stop` direkt erhält -- ohne `exec` würde die Shell das Signal
      schlucken und der Container liefe in den 10-Sekunden-Timeout.

      Die Datei muss **LF**-Zeilenenden haben; mit CRLF scheitert der Start an
      `/bin/sh^M: bad interpreter`. Absicherung auf zwei Ebenen: beim Schreiben
      explizit LF, und in `.gitattributes` die Regel
      `entrypoint.sh text eol=lf` gegen die globale `* text=auto`-Normalisierung
      auf einem Windows-Checkout.

- [ ] **Schritt 4: .dockerignore** -- ausgeschlossen werden `.git/`,
      `.gitattributes`, `.venv/`, `venv/`, `__pycache__/`, `*.py[cod]`,
      `db.sqlite3*`, `.env`, `staticfiles/`, `media/`, `.workflow/`,
      `.github/`, `.idea/`, `.vscode/`, `Dockerfile`, `docker-compose.yml`,
      `*.md`. Damit enthält der Build-Context nur Anwendungscode, `manage.py`
      und die Requirements-Dateien.

- [ ] **Schritt 5: docker-compose.yml** --
      Ein Service `web` mit `build: .`, `ports: ["8000:8000"]`, einem benannten
      Volume `dbdata:/data` für die SQLite-Datei und
      ```yaml
      env_file:
        - path: .env
          required: false
      ```
      Die `required: false`-Form sorgt dafür, dass `docker compose up` auch ohne
      lokale `.env` startet. Zusätzlich gesetzt werden nur unkritische Defaults
      (`DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`) --
      keine Secrets im Versionsstand. Kein `version:`-Schlüssel, der ist in
      aktuellen Compose-Versionen obsolet und erzeugt eine Warnung.

- [ ] **Schritt 6: .github/workflows/ci.yml** --
      Zwei Jobs auf `ubuntu-latest`, Trigger:
      ```yaml
      on:
        push:
          branches: [main]
        pull_request:
          branches: [main]
      permissions:
        contents: read
      ```
      *Job `test`:* `actions/checkout@v4` → `actions/setup-python@v5` mit
      `python-version: "3.12"` und `cache: pip` (als `cache-dependency-path`
      beide Requirements-Dateien) → `pip install -r requirements-dev.txt` →
      `ruff check .` → `python manage.py check` →
      `python manage.py makemigrations --check --dry-run` →
      `python manage.py test`.

      *Job `docker`:* `actions/checkout@v4` → `docker build -t learning-companion:ci .`
      Ein kaputtes Dockerfile färbt die CI damit rot, ohne dass ein Image
      irgendwohin gepusht wird.

      Keine `secrets`-Referenzen: ohne `OPENAI_API_KEY` läuft der AI-Service im
      Mock-Modus, die Testsuite ist davon unabhängig (belegt durch Feature 4).

- [ ] **Schritt 7: Dokumentation** -- `.env.example` um `DJANGO_DB_PATH` und
      `DJANGO_STATIC_ROOT` ergänzen, jeweils mit Kommentar und leerem bzw.
      auskommentiertem Wert (die Defaults aus `settings.py` greifen).

- [ ] **Schritt 8: Validierung** -- siehe Abschnitt 4. Docker ist in dieser
      Umgebung verfügbar (29.7.2), der Build und ein Container-Smoke-Test werden
      daher **real ausgeführt**, nicht nur syntaktisch geprüft.

## 4. Validierung & Test-Strategie

Das Feature ist Infrastruktur -- es entstehen keine neuen Django-Unit-Tests. Die
Validierung erfolgt stattdessen gegen die realen Werkzeuge:

| # | Prüfung | Kommando | Erwartung |
|---|---|---|---|
| 1 | Bestandstests nach Settings-Änderung | `python manage.py test` | 145 Tests, OK |
| 2 | System-Check | `python manage.py check` | 0 Issues |
| 3 | Migrationsfreiheit | `python manage.py makemigrations --check --dry-run` | No changes detected |
| 4 | `collectstatic` lauffähig | `python manage.py collectstatic --noinput` | läuft durch (vorher: `ImproperlyConfigured`) |
| 5 | Linter | `ruff check .` | keine Befunde |
| 6 | Image-Build | `docker build -t learning-companion:ci .` | Exit 0 |
| 7 | Non-Root | `docker run --rm learning-companion:ci id -u` | Ausgabe != 0 |
| 8 | Keine Secrets im Image | `docker history --no-trunc` + `docker run --rm ... env` | kein `sk-`, kein echter `SECRET_KEY` |
| 9 | Entrypoint-Zeilenenden | Prüfung auf `\r` in `entrypoint.sh` | kein Treffer |
| 10 | Container-Smoke-Test | `docker compose up -d`, dann HTTP-Request auf `:8000` | Status 200 oder Redirect, Migration + collectstatic im Log |
| 11 | Statische Dateien bei `DEBUG=False` | Request auf eine Admin-CSS-Datei | Status 200, nicht 404 |
| 12 | Compose-Syntax | `docker compose config` | validiert fehlerfrei |
| 13 | CI-Workflow-Syntax | YAML-Parse des Workflows + Prüfung der Trigger/Steps | `push`+`pull_request` auf `main`, Cache, alle vier Prüfschritte vorhanden |
| 14 | Hook | `.\.workflow\hooks\validate_code.ps1` | Exit-Code 0 |

**Besonderes Augenmerk** liegt auf Prüfung 7, 10 und 11: Die Kombination
"unprivilegierter Benutzer" + "SQLite schreibt ins Dateisystem" +
"`collectstatic` schreibt nach `STATIC_ROOT`" ist genau die Stelle, an der ein
sonst korrektes Dockerfile beim ersten Start scheitert. Ein reiner `docker build`
würde das nicht aufdecken -- deshalb wird der Container tatsächlich gestartet
und ein Request abgesetzt.

**Abnahmekriterium:** `validate_code.ps1` endet mit Exit-Code 0 **und** die
Prüfungen 6, 7, 10 und 12 sind real durchgeführt und dokumentiert.
