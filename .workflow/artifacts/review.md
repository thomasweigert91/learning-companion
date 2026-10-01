# Code Review: Containerisierung und Continuous Integration

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, gunicorn 23.0.0, whitenoise 6.12.0, ruff 0.16.9, Docker 29.7.2.
**145 Tests** unverändert grün, `ruff check .` ohne Befund, `validate_code.ps1` Exit-Code 0.

> **Docker war real verfügbar.** Der Daemon lief zunächst nicht; Docker Desktop wurde gestartet, anschließend wurden Build **und** Laufzeitverhalten tatsächlich ausgeführt. Dieses Review stützt sich damit nicht auf einen Syntax-Check, sondern auf einen laufenden Container.

Neue Dateien: `Dockerfile`, `.dockerignore`, `entrypoint.sh`, `docker-compose.yml`, `.github/workflows/ci.yml`, `requirements-dev.txt`, `pyproject.toml`
Geändert: `requirements.txt`, `learning_companion/settings.py`, `.env.example`, `.gitattributes`, `core/services/ai_service.py`

---

## 1. Abdeckung der Akzeptanzkriterien

### Dockerfile

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | Multi-Stage auf `python:3.12-slim` | `builder` baut Wheels, `runtime` installiert daraus | ja |
| 2 | Keine Build-Toolchain in der Runtime | `command -v gcc cc` im Container → "keine Compiler gefunden" | ja |
| 3 | Unprivilegierter Benutzer, UID != 0 | `docker run --rm --entrypoint id … -u` → **1000**; `whoami` → `app` | ja |
| 4 | gunicorn als Anwendungsprozess, mit Versionsgrenze | `CMD` ruft `learning_companion.wsgi:application`; `gunicorn>=23.0,<24.0`, installiert 23.0.0 | ja |
| 5 | Port 8000, gebunden an `0.0.0.0` | `EXPOSE 8000`, `--bind 0.0.0.0:8000`; Log: "Listening at: http://0.0.0.0:8000" | ja |
| 6 | Keine Secrets im Image | siehe Abschnitt 2 | ja |
| 7 | `PYTHONDONTWRITEBYTECODE`/`PYTHONUNBUFFERED` | in beiden Stages gesetzt | ja |

### Entrypoint

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 8 | `migrate` → `collectstatic` → `exec "$@"` | Container-Log zeigt beide Schritte vor dem gunicorn-Start | ja |
| 9 | `#!/bin/sh` + `set -e` | `od -c` auf die erste Zeile im Image: `# ! / b i n / s h \n` | ja |
| 10 | LF-Zeilenenden, ausführbar | 0 CR-Bytes in der Datei; im Image `-rwxr-xr-x`; `.gitattributes` setzt `*.sh text eol=lf` | ja |

**gunicorn läuft tatsächlich als PID 1** — im Log booten die Worker mit PID 29/30/31 unter dem Master mit `[1]`. `exec` greift also; ein `docker stop` erreicht den Prozess direkt, statt in den 10-Sekunden-Timeout zu laufen.

### Konfiguration

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 11 | `STATIC_ROOT` gesetzt, `collectstatic` läuft | lokal: "127 static files copied, 381 post-processed"; im Container identisch | ja |
| 12 | `DJANGO_DB_PATH` konfigurierbar, Default unverändert | `os.environ.get("DJANGO_DB_PATH") or BASE_DIR / "db.sqlite3"` | ja |
| 13 | Statische Dateien bei `DEBUG=False` | Container meldet `DEBUG = False`; `/admin/login/` → 200, darin `/static/admin/css/base.96c479cedf7a.css` → **200, 22285 Bytes** | ja |
| 14 | `.env.example` dokumentiert die neuen Variablen | beide Variablen mit Kommentar ergänzt | ja |

Der gehashte Dateiname belegt nebenbei, dass `CompressedManifestStaticFilesStorage` wirklich greift und nicht stillschweigend auf den Default zurückfällt.

### .dockerignore, Compose, CI

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 15 | Ausschlüsse vollständig | `.venv/`, `.git/`, `db.sqlite3`, `__pycache__/`, `*.py[cod]`, `.env`, `staticfiles/`, `.workflow/` — alle vorhanden | ja |
| 16 | Build-Context klein | `transferring context: 4.99kB` gegenüber einem Arbeitsverzeichnis mit `.venv` und `.git` im dreistelligen MB-Bereich | ja |
| 17 | Compose baut und mappt Port 8000 | `docker compose up -d` → HTTP 200 auf `localhost:8000` | ja |
| 18 | Optionale `.env`, keine Secrets im Versionsstand | `env_file: [{path: .env, required: false}]`; gesetzt sind nur `DJANGO_DEBUG` und `DJANGO_ALLOWED_HOSTS` | ja |
| 19 | Benanntes Volume, Daten überleben `down`/`up` | **real geprüft**: Nutzer angelegt → `docker compose down` → `up` → `ueberlebt: True` | ja |
| 20 | `docker compose config` validiert | Exit-Code 0 | ja |
| 21 | Trigger `push` + `pull_request` auf `main` | YAML geparst: `{'push': {'branches': ['main']}, 'pull_request': {'branches': ['main']}}` | ja |
| 22 | Python 3.12 + pip-Caching | `actions/setup-python@v5`, `cache: pip`, `cache-dependency-path` über beide Requirements-Dateien | ja |
| 23 | Linter, Check, Migrationsprüfung, Tests | Steps geparst: Linter → Django System-Check → "Migrationen vollstaendig?" → Testsuite | ja |
| 24 | `permissions: contents: read`, Actions gepinnt | gesetzt; `@v4`/`@v5`, kein `@master` | ja |
| 25 | Zweiter Job baut das Image | Job `docker` mit `docker build` | ja |
| 26 | CI ohne Secrets | keine `secrets.`-Referenz im Workflow; ohne `OPENAI_API_KEY` greift der Mock-Modus | ja |

### Validierung

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 27 | `docker build` fehlerfrei | `BUILD-EXIT=0`, Image 303 MB | ja |
| 28 | Container startet und antwortet | Migration + collectstatic im Log, `GET /` → **200** | ja |
| 29 | `ruff check` ohne Befund | "All checks passed!" | ja |
| 30 | 145 Tests weiterhin grün | `Ran 145 tests — OK` nach der Settings-Änderung | ja |

---

## 2. Sicherheit

### Keine Secrets im Image

Vier unabhängige Prüfungen, alle am gebauten Image durchgeführt:

| Prüfung | Ergebnis |
|---|---|
| `docker run --rm --entrypoint env` nach `SECRET\|OPENAI\|KEY\|PASSWORD` | ein Treffer: `GPG_KEY=7169605F…` |
| `/app/.env` vorhanden? | nein |
| `/app/db.sqlite3` vorhanden? | nein |
| `docker history --no-trunc` nach `sk-` | 0 Treffer |

**Zum `GPG_KEY`-Treffer:** Der stammt aus dem offiziellen `python:3.12-slim`-Basisimage und ist der *öffentliche* Signaturschlüssel-Fingerprint der Python-Release-Manager, mit dem das Tarball beim Bau verifiziert wird. Ein öffentlicher Fingerprint, kein Geheimnis — er ist in jedem offiziellen Python-Image enthalten und wird vom Grep nur wegen der Zeichenfolge "KEY" erfasst. Kein Befund.

Das Image enthält weder `DJANGO_SECRET_KEY` noch `OPENAI_API_KEY` als `ENV` oder `ARG`. Gesetzt sind ausschließlich Pfade (`DJANGO_DB_PATH`, `DJANGO_STATIC_ROOT`). Die `.dockerignore` schließt `.env` zusätzlich aus, sodass auch ein versehentliches `COPY . .` den Schlüssel nicht einzöge — zwei unabhängige Schichten.

### Non-root

`USER app` steht **vor** `ENTRYPOINT`/`CMD`, greift also für den Anwendungsprozess und nicht erst für spätere Layer. UID 1000, kein Home-Verzeichnis, `/usr/sbin/nologin` als Shell. Die Verzeichnisrechte sind passend gesetzt: `/data` und `/app/staticfiles` gehören `app:app`, der Anwendungscode gehört ihm über `COPY --chown`.

Das `entrypoint.sh` gehört bewusst `root` mit `0755` — der unprivilegierte Prozess darf es ausführen, aber nicht verändern. Das ist die richtige Richtung; ein `--chown=app` auf das Entrypoint-Script wäre eine unnötige Angriffsfläche.

**Der kritische Punkt an dieser Stelle** ist die Kombination aus Non-Root und SQLite: SQLite legt neben der Datenbank eine Journal-Datei an und braucht deshalb Schreibrechte auf das *Verzeichnis*, nicht nur auf die Datei. Ein Dockerfile, das nur `chown` auf die DB-Datei setzt, baut sauber und scheitert erst beim ersten Schreibzugriff zur Laufzeit. Hier ist `/data` als Ganzes übereignet, und der Laufzeit-Test belegt, dass Migration und Schreibzugriff funktionieren.

### CI

- `permissions: contents: read` — der Workflow kann nichts schreiben, auch nicht bei einem kompromittierten Step.
- Actions auf Major-Versionen gepinnt (`@v4`, `@v5`), kein `@master`.
- Keine `secrets`-Referenz, keine `pull_request_target`-Verwendung (die Fremd-PRs Zugriff auf Secrets gäbe).
- Der `docker`-Job baut nur und pusht nicht; es sind keine Registry-Zugangsdaten im Spiel.

### Weitere Prüfungen

- **Angriffsfläche Image:** keine Build-Toolchain, kein `curl`/`wget`-Install, keine zusätzlichen apt-Pakete in der Runtime.
- **`ALLOWED_HOSTS`:** bleibt umgebungsgesteuert; die Compose-Datei setzt den restriktiven Default `localhost,127.0.0.1` statt `*`.
- **`DEBUG`:** die Compose-Datei setzt explizit `False` — ein Container mit aktivem Debug-Modus und damit einsehbaren Settings wäre der klassische Fehler an dieser Stelle.

---

## 3. Code-Qualität

**Positiv:**

- Die Settings-Änderungen sind strikt rückwärtskompatibel: `os.environ.get(...) or BASE_DIR / ...` lässt die lokale Entwicklung unverändert. Die `or`-Form statt eines zweiten Arguments fängt zusätzlich den Fall ab, dass die Variable *gesetzt, aber leer* ist — genau das, was `.env.example` mit `DJANGO_DB_PATH=` vorgibt. Mit `os.environ.get("DJANGO_DB_PATH", default)` wäre der Pfad in dem Fall der leere String gewesen und Django hätte beim Start eine unbrauchbare Datenbank konfiguriert. Der Unterschied ist subtil und hier richtig gelöst.
- Die drei nicht offensichtlichen Stellen sind im Code begründet, nicht stillschweigend gelöst: `exec` im Entrypoint (Signal-Weiterreichung), `/data`-Ownership (SQLite-Journal), WhiteNoise-Position in der Middleware-Kette.
- `requirements-dev.txt` trennt den Linter sauber vom Laufzeit-Image; `ruff` landet nicht im Container.
- Kein `version:`-Schlüssel in der Compose-Datei — in aktuellen Compose-Versionen obsolet und nur eine Warnquelle.

**Während des Reviews behoben:** `ruff` meldete drei `B904`-Verstöße in `core/services/ai_service.py` (Feature 4): In den `except`-Blöcken wurde `AIServiceError` ohne `from` geworfen. Das ist kein kosmetischer Befund — ohne explizites `from None` hängt Python die Originalausnahme als `__context__` an, und ein Traceback hätte den SDK-Fehler mitsamt möglichem Schlüsselfragment weitergetragen. Genau das wollte der Code laut eigenem Kommentar ("weder Stacktrace noch SDK-Rohtext noch ein Key-Fragment beim Nutzer") verhindern. Mit `raise … from None` ist die Absicht jetzt auch technisch umgesetzt. Die Tests bleiben unverändert grün.

**Eine Anmerkung ohne Nachbesserungsbedarf:** Das Image ist mit 303 MB nicht winzig. Der Löwenanteil stammt aus dem `openai`-SDK samt `pydantic`-Abhängigkeiten, nicht aus vermeidbarem Ballast — die Runtime-Stage enthält nachweislich keine Build-Werkzeuge. Ein `alpine`-Basisimage würde Größe gegen musl-Kompatibilitätsrisiken tauschen; das lohnt hier nicht.

---

## 4. Abweichungen gegenüber dem Plan

| Abweichung | Bewertung |
|---|---|
| Zusätzlich `pyproject.toml` mit `[tool.ruff]`. | War in den betroffenen Dateien des Plans bereits gelistet; stellt sicher, dass lokal und in der CI derselbe Regelsatz greift. |
| `core/services/ai_service.py` geändert (B904). | Nicht geplant, aber notwendig: ohne die Korrektur wäre der neue CI-Linter-Step beim ersten Lauf rot. Ein Feature, das eine Prüfung einführt, muss den Bestand durch diese Prüfung bringen. |
| `.gitattributes` um `*.sh text eol=lf` erweitert. | Im Plan als Absicherung vorgesehen und umgesetzt. |

Keine Abweichung verändert den fachlichen Umfang des Tickets.

---

## 5. Migrationen

Keine Modell-Änderung, keine neue Migration. `makemigrations --check --dry-run` meldet "No changes detected" — und prüft das ab jetzt bei jedem CI-Lauf automatisch mit.

---

## 6. Verifikation

```powershell
ruff check .                                        # All checks passed!
python manage.py check                              # 0 Issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py collectstatic --noinput            # 127 Dateien, 381 post-processed
python manage.py test                               # Ran 145 tests — OK
.\.workflow\hooks\validate_code.ps1                 # Exit-Code 0

docker build -t learning-companion:ci .             # Exit 0, 303 MB
docker run --rm --entrypoint id … -u                # 1000 (non-root)
docker compose config --quiet                       # Exit 0
docker compose up -d                                # GET / -> 200
docker compose down && docker compose up -d         # Daten ueberlebt: True
```

Alle Container-Prüfungen wurden real ausgeführt. Der Testnutzer aus der Persistenzprobe und das Volume wurden anschließend entfernt (`docker compose down -v`).

---

## 7. Fazit

Alle 30 Akzeptanzkriterien des Tickets sind erfüllt und jeweils durch eine konkrete Messung oder Codestelle belegt. Der Container läuft unprivilegiert, enthält keine Secrets, startet reproduzierbar inklusive Migration und `collectstatic` und beantwortet Requests; die Daten überstehen einen Neustart. Die CI prüft Linter, System-Check, Migrationsvollständigkeit, Testsuite und den Image-Build, ohne Secrets zu benötigen und ohne Schreibrechte zu verlangen.

Ein echter Befund wurde im Zuge des Reviews gefunden und behoben (B904-Exception-Verkettung im AI-Service). Darüber hinaus keine offenen Punkte.

**Freigabe erteilt: APPROVED.**
