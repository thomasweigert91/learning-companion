# Learning Companion

[![CI](https://github.com/thomasweigert91/learning-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/thomasweigert91/learning-companion/actions/workflows/ci.yml)

Eine Django-Webanwendung, mit der Lernende ihre **Lernziele**, **Lernsitzungen** und **Lernressourcen** verwalten, ihren Fortschritt in einem **Dashboard** auswerten und sich von einer **KI (OpenAI)** Zusammenfassungen und nächste Lernschritte vorschlagen lassen.

Jeder Nutzer sieht ausschließlich seine eigenen Daten.

---

## Funktionen

### Konto & Profil
- Registrierung, Login und Logout (Logout als POST, wie von Django 5 gefordert).
- Eigenes Profil mit Name, Cohort und **Focus Areas** (Tags).
- Passwörter laufen über die Standard-Validierung und das Hashing von `django.contrib.auth`.

### Lernziele (Goals)
- Lernziele anlegen, bearbeiten und löschen, jeweils mit Titel, Beschreibung und Status: **Geplant**, **In Arbeit** oder **Erledigt**.
- Die Übersicht lässt sich nach Status filtern und zeigt die Ziele als Karten mit farbigem Status-Badge.
- Wird ein Lernziel gelöscht, werden seine Sitzungen, Ressourcen und sein KI-Verlauf mitgelöscht.

### Lernsitzungen (Sessions)
- Lernzeit pro Lernziel erfassen: Datum, Dauer in Minuten (mindestens 1), Notizen und Tags.
- Übersichtstabelle mit allen Sitzungen und ihren Tags.
- Bei der Auswahl des Lernziels werden nur eigene Ziele angeboten. Ein manipulierter Request mit einer fremden Goal-ID wird serverseitig abgelehnt.

### Ressourcen
- Links an ein Lernziel anhängen, z. B. Artikel, Videos, Repositories oder Dokumentation.
- Jeder Typ hat ein eigenes Badge, externe Links öffnen in einem neuen Tab.
- Die URL muss gültig sein und der Titel ist Pflicht. Bei ungültigen Eingaben erscheinen die Fehler direkt am Feld, die vorhandenen Ressourcen bleiben sichtbar.

### Dashboard
- **Kennzahlen:** Anzahl der Lernziele, Anzahl der Sitzungen und die gesamte Lernzeit.
- **Lernziele nach Status:** Anzahl je Status; ein Status ohne Ziele erscheint mit 0.
- **Lernzeit je Kategorie:** Summe der Minuten je Tag. Eine Sitzung mit mehreren Tags zählt in jede ihrer Kategorien.
- **Lernzeit je Kalenderwoche:** Minuten pro Woche, jeweils ab Montag.
- Alle Werte berechnet die Datenbank per ORM-Aggregation (`Count`, `Sum`, `TruncWeek`), nicht eine Schleife in Python.

### KI-Unterstützung (OpenAI)
- **Zusammenfassung generieren:** eine kurze Einschätzung des Fortschritts, gebildet aus den Sitzungen und Ressourcen des Lernziels.
- **Nächste Schritte vorschlagen:** 2–3 konkrete nächste Lernschritte.
- **KI-Verlauf:** Jedes erfolgreiche Ergebnis wird gespeichert und als Zeitleiste angezeigt, neueste Einträge zuerst. Einträge lassen sich einzeln löschen oder gesammelt zurücksetzen (mit Bestätigungsseite).
- **Ladezustand:** Während eine Anfrage läuft, zeigt der geklickte Button einen Spinner, und beide Buttons sind gesperrt. Doppelte Anfragen sind damit ausgeschlossen.
- **Mock-Modus:** Ohne API-Schlüssel, oder mit `AI_MOCK_MODE=True`, liefert die App deterministische Platzhalter-Antworten. Lokal funktioniert also alles auch ohne OpenAI-Konto und ohne Kosten.
- In den Prompt gelangen nur Daten des jeweiligen Lernziels. Fehler wie Timeout oder Rate-Limit erscheinen als verständliche Meldung und nie als Stacktrace.

### Export & Backup
Unter **Export** (`/export/`) lassen sich die eigenen Daten herunterladen:
- **Lernsitzungen als CSV:** Spalten `Goal, Date, Duration (min), Tags, Notes`, chronologisch sortiert. Die Datei hat ein UTF-8-BOM, damit Excel Umlaute richtig anzeigt, und wird zeilenweise gestreamt. Zellen, die mit `=`, `+`, `-` oder `@` beginnen, bekommen ein führendes `'`, damit eine Tabellenkalkulation sie nicht als Formel ausführt.
- **Goals als Markdown-ZIP:** eine Datei `goals/<id>-<slug>.md` je Lernziel, mit YAML-Frontmatter (Status, Zeitstempel, Anzahl Sitzungen, Minuten), Ressourcen und Sitzungshistorie. Gut geeignet für Obsidian, ein Wiki oder Git.
- **Vollständiges Backup als JSON:** Konto, Profil, Lernziele mit Sitzungen, Ressourcen, KI-Verlauf und Lernkarten sowie die Kennzahlen des Dashboards. Gedacht für die Datenübertragbarkeit nach Art. 20 DSGVO. Passwort-Hash und Berechtigungs-Flags sind nicht enthalten.
- Jeder Export enthält ausschließlich Daten des angemeldeten Nutzers. Die Downloads werden nicht gecacht (`Cache-Control: no-store`).

### Oberfläche
- Responsives Design mit **Bootstrap 5.3** und **Bootstrap Icons**, per CDN mit Subresource Integrity eingebunden.
- Barrierearm umgesetzt: Skip-Link, Landmarks, Formularfehler sind per ARIA mit den Feldern verknüpft, Tabellen haben Captions, Fortschrittsbalken tragen ARIA-Werte, und Status wird nie nur über Farbe vermittelt.

---

## Tech-Stack

| Bereich | Technologie |
|---|---|
| Backend | Python 3.12, Django 5.2 |
| Datenbank | SQLite |
| KI | OpenAI Python SDK (Standardmodell `gpt-4o-mini`) |
| Frontend | Django-Templates, Bootstrap 5.3, Vanilla JavaScript |
| Betrieb | gunicorn, WhiteNoise, Docker (Multi-Stage), Docker Compose |
| Qualität | Django-Testsuite, ruff, GitHub Actions |

---

## Schnellstart (lokal)

Voraussetzung: Python 3.12.

```powershell
# 1. Virtuelle Umgebung anlegen und aktivieren
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate

# 2. Abhängigkeiten installieren (inkl. ruff für die Entwicklung)
pip install -r requirements-dev.txt

# 3. Optional: lokale Konfiguration anlegen
copy .env.example .env                 # Linux/macOS: cp .env.example .env

# 4. Datenbank anlegen und Server starten
python manage.py migrate
python manage.py runserver
```

Die App läuft danach unter **http://127.0.0.1:8000/**.

Tags (Focus Areas, Sitzungs-Tags) werden im Django-Admin gepflegt. Dafür einmal einen Admin-Nutzer anlegen:

```powershell
python manage.py createsuperuser
```

Der Admin ist dann unter http://127.0.0.1:8000/admin/ erreichbar.

---

## Konfiguration

Die Einstellungen kommen aus Umgebungsvariablen. Eine lokale `.env` im Projektverzeichnis wird beim Start automatisch geladen (`python-dotenv`). Bereits gesetzte Umgebungsvariablen haben dabei Vorrang. Die `.env` wird **nicht** versioniert; als Vorlage dient `.env.example`.

| Variable | Standard | Bedeutung |
|---|---|---|
| `DJANGO_SECRET_KEY` | unsicherer Entwicklungswert | **In Produktion zwingend setzen.** |
| `DJANGO_DEBUG` | `True` | In Produktion `False`. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Kommagetrennte Hostnamen. |
| `DJANGO_DB_PATH` | `db.sqlite3` im Projekt | Pfad der SQLite-Datei. |
| `DJANGO_STATIC_ROOT` | `staticfiles/` im Projekt | Ziel von `collectstatic`. |
| `OPENAI_API_KEY` | leer | Leer bedeutet Mock-Modus. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Verwendetes Modell. |
| `OPENAI_TIMEOUT_SECONDS` | `20` | Timeout pro API-Versuch. |
| `AI_MOCK_MODE` | `False` | `True` erzwingt den Mock, auch wenn ein Schlüssel gesetzt ist. |

> **Kosten:** Mit gesetztem `OPENAI_API_KEY` löst jeder Klick auf eine KI-Aktion einen kostenpflichtigen API-Aufruf aus. Die Testsuite ist davon ausgenommen (siehe [Tests](#tests)).

---

## Docker

Das Image baut in zwei Stufen auf `python:3.12-slim` auf und läuft als **nicht privilegierter Benutzer** mit **gunicorn**. Beim Start führt das Entrypoint-Script die Migrationen und `collectstatic` aus, danach liefert WhiteNoise die statischen Dateien aus.

```bash
docker compose up --build
```

- Die App ist danach unter **http://localhost:8000/** erreichbar.
- Die SQLite-Datenbank liegt im benannten Volume `dbdata` und übersteht `docker compose down`.
- Eine vorhandene `.env` wird automatisch eingelesen, ist aber nicht nötig. Secrets landen nie im Image.

Nach Änderungen an `requirements.txt` das Image neu bauen (`docker compose build`).

---

## Tests

```powershell
python manage.py test        # Testsuite
ruff check .                 # Linter
python manage.py check       # Django-System-Check
```

Die Suite umfasst **über 200 Tests**. Sie prüfen unter anderem die Mandantentrennung (fremde Daten führen zu 404), die Dashboard-Aggregationen, die Formulare, die KI-Aktionen samt Fehlerpfaden und den gespeicherten Verlauf sowie die Barrierefreiheit der Oberfläche.

Die Tests erreichen **niemals** die echte OpenAI-API. Ein eigener Test-Runner (`core/test_runner.py`) erzwingt im gesamten Testlauf den Mock-Modus, auch wenn die `.env` einen echten Schlüssel enthält. Tests, die den echten API-Pfad prüfen, ersetzen das SDK durch Attrappen.

---

## Continuous Integration

GitHub Actions (`.github/workflows/ci.yml`) läuft bei jedem Push und Pull Request auf `main`:

1. **Lint, Checks und Tests:** ruff, `manage.py check`, Prüfung auf fehlende Migrationen und die komplette Testsuite.
2. **Docker-Image bauen:** Ein fehlerhaftes Dockerfile lässt die CI fehlschlagen.

Die CI kommt ohne Secrets aus und hat nur Leserechte auf das Repository.

---

## Projektstruktur

```
learning_companion/        Django-Projekt (Settings, Root-URLs, WSGI)
core/
  models.py                Profile, Tag, Goal, LearningSession, Resource, AIFeedback
  views.py                 Alle Views, strikt auf den angemeldeten Nutzer gefiltert
  forms.py                 Formulare (Registrierung, Profil, Goal, Session, Ressource)
  services/ai_service.py   Einzige Stelle, die das OpenAI-SDK kennt
  services/export_service.py  CSV-, Markdown-ZIP- und JSON-Export (nur lesend)
  templatetags/ui.py       Bootstrap-Helfer für Formulare und Navigation
  templates/               Django-Templates
  tests/                   Testsuite
  test_runner.py           Test-Runner mit erzwungenem KI-Mock
.github/workflows/ci.yml   CI-Pipeline
Dockerfile, entrypoint.sh, docker-compose.yml
.workflow/                 Spezifikations- und Review-Pipeline (Ticket → Plan → Code → Review)
```

---

## Sicherheit im Überblick

- **Mandantentrennung:** Alle Abfragen gehen vom angemeldeten Nutzer aus. Wer fremde IDs anfragt, bekommt eine 404, bevor irgendetwas gelesen oder geändert wird.
- **Löschen nur per POST** mit CSRF-Token, nie per GET.
- **Keine Secrets im Repository oder Image:** `.env` ist durch `.gitignore` und `.dockerignore` ausgeschlossen, der API-Schlüssel wird ausschließlich aus der Umgebung gelesen.
- KI-Antworten werden als nicht vertrauenswürdige Eingabe behandelt und immer escaped ausgegeben.
- Clickjacking-Schutz (`X-Frame-Options: DENY`) und Subresource Integrity für alle CDN-Ressourcen.
