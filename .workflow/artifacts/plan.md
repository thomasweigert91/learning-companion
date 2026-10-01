# Implementierungs-Plan: AI-powered summary and next steps — Service-Layer, Mock-Strategie und Fehlerbehandlung

## 1. Betroffene Dateien

**Neu — Service-Layer**

- Neu: `core/services/__init__.py`
- Neu: `core/services/ai_service.py` — gesamte OpenAI-Anbindung, Prompt-Bau, Fehler-Übersetzung, Mock-Modus

**Ändern**

- Ändern: `requirements.txt` — `openai` ergänzen
- Ändern: `.env.example` — `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_MOCK_MODE` dokumentieren
- Ändern: `learning_companion/settings.py` — die drei Einstellungen aus der Umgebung lesen
- Ändern: `core/views.py` — `GoalSummaryView` und `GoalNextStepsView` ergänzen, `GoalDetailView` um die Ergebnisse aus der Session erweitern
- Ändern: `core/urls.py` — zwei Routen ergänzen
- Ändern: `core/templates/base.html` — Django-Messages ausgeben (bislang nicht vorhanden)
- Ändern: `core/templates/core/goal_detail.html` — zwei Aktions-Formulare und die Ergebnisbereiche

**Neu — Tests**

- Neu: `core/tests/test_ai_service.py` — Service im Mock-Modus, Prompt-Inhalt, Fehler-Übersetzung
- Neu: `core/tests/test_ai_views.py` — beide Views, Anzeige, Fehlerpfade, Scoping

**Unverändert:** `core/models.py`, `core/forms.py`, `core/admin.py`, alle Migrationen (dieses Feature bringt **kein** neues Modell mit) sowie alle bestehenden Testmodule.

## 2. Datenmodelle & Migrationen

**Es werden keine Modelle geändert und keine Migration erzeugt.**

Das ist eine bewusste Entscheidung und zugleich ein Akzeptanzkriterium: Generierte Zusammenfassungen sind Momentaufnahmen über einen Datenbestand, der sich mit der nächsten Lernsitzung ändert. Würden sie persistiert, entstünde sofort die Frage nach Invalidierung und Veralterung — ein Problem, das das Ticket nicht stellt.

**Ablage der Ergebnisse: Django-Session.**

```
request.session["ai_summary"]     = {"goal_id": <pk>, "text": "..."}
request.session["ai_next_steps"]  = {"goal_id": <pk>, "steps": ["...", "...", "..."]}
```

Der Schlüssel trägt die `goal_id` mit, damit `GoalDetailView` ein Ergebnis nur dann anzeigt, wenn es zum gerade betrachteten Goal gehört. Ohne diesen Abgleich würde eine Zusammenfassung von Goal A auch unter Goal B erscheinen. Da die Session serverseitig gehalten wird und an den angemeldeten Nutzer gebunden ist, verlässt kein Ergebnis den Besitzer.

**Begrenzung des Prompt-Kontexts.** Es werden höchstens die jüngsten 10 Lernsitzungen und 20 Ressourcen übergeben (Konstanten `MAX_SESSIONS` und `MAX_RESOURCES` im Service). Ohne Obergrenze würde der Prompt mit der Datenmenge wachsen und irgendwann das Kontextfenster oder das Kostenbudget sprengen.

**Settings** (`learning_companion/settings.py`):

```python
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "20"))
AI_MOCK_MODE = os.environ.get("AI_MOCK_MODE", "") == "True"
```

Kein Default-Key, kein Fallback-Literal. Fehlt der Key, bleibt der Wert leer — der Service schaltet dann selbsttätig in den Mock-Modus, statt beim Start zu scheitern. `manage.py check` läuft damit auch ohne Key durch.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Abhängigkeit und Konfiguration** — `openai>=1.40,<2.0` in `requirements.txt` eintragen und im `.venv` installieren; `.env.example` um die drei Variablen ergänzen — `OPENAI_API_KEY` bleibt dort **leer**, es wird bewusst kein realistisch aussehender Beispielschlüssel hinterlegt, auch kein erfundener; die vier Einstellungen in `settings.py` ergänzen. Abnahme: `manage.py check` Exit-Code 0 **ohne** gesetzten Key.

- [ ] **Schritt 2: Service-Layer, Gerüst und Mock-Modus** — `core/services/ai_service.py` anlegen mit:
  - `class AIServiceError(Exception)` — die einzige Exception, die den Service verlässt.
  - `def is_mock_mode()` → `settings.AI_MOCK_MODE or not settings.OPENAI_API_KEY`. Damit ist der Mock aktiv, sobald er eingeschaltet ist **oder** kein Key vorliegt; die Anwendung bleibt lokal ohne Key benutzbar.
  - Konstanten `MAX_SESSIONS = 10`, `MAX_RESOURCES = 20`.
  
  Der Mock liefert deterministische, aus den echten Goal-Daten abgeleitete Ergebnisse (Titel, Anzahl Sessions, Gesamtdauer), damit die Oberfläche im Mock-Betrieb plausibel aussieht und nicht nur Platzhalter zeigt.

- [ ] **Schritt 3: Prompt-Bau** — Zwei private Funktionen `_build_summary_prompt(goal)` und `_build_next_steps_prompt(goal)`. Beide lesen ausschließlich über die Beziehungen des übergebenen Goals (`goal.sessions.all()[:MAX_SESSIONS]`, `goal.resources.all()[:MAX_RESOURCES]`) — es gibt im Service keine einzige Query, die nicht von diesem Goal ausgeht. Daraus folgt strukturell, dass keine Fremddaten in den Prompt geraten können; ein Test prüft es zusätzlich explizit.
  
  Die Prompts fordern deutschsprachige Ausgabe an. Für die nächsten Schritte wird eine zeilenweise Liste angefordert und die Antwort serverseitig in eine Python-Liste zerlegt und auf 2 bis 3 Einträge begrenzt — die Längenzusage wird also nicht dem Modell überlassen, sondern im Code durchgesetzt.

- [ ] **Schritt 4: API-Aufruf und Fehler-Übersetzung** — `_call_openai(prompt)` kapselt den einzigen SDK-Kontakt:
  - Client als `OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=1)`. Explizites Timeout, damit ein hängender Aufruf keinen Request-Thread dauerhaft blockiert; `max_retries=1`, damit ein Rate-Limit nicht zu langen Wartezeiten im Request führt.
  - Aufruf über `client.chat.completions.create(model=settings.OPENAI_MODEL, messages=[...])`.
  - `except APITimeoutError` → `AIServiceError` mit der Meldung zum Timeout.
  - `except RateLimitError` → `AIServiceError` mit eigener Meldung.
  - `except Exception` → `AIServiceError` mit einer generischen Meldung. Der ursprüngliche Fehler wird per `logger.exception()` protokolliert, aber **nicht** in die Nutzermeldung übernommen — so landen weder Stacktrace noch SDK-Rohtext noch ein Key-Fragment in der Oberfläche.
  
  Der Import der SDK-Fehlertypen erfolgt modulweit; das SDK ist damit ausschließlich in dieser Datei bekannt.

- [ ] **Schritt 5: Öffentliche Service-Funktionen** — `generate_summary(goal)` → `str` und `suggest_next_steps(goal)` → `list[str]`. Beide prüfen zuerst `is_mock_mode()` und liefern in dem Fall das Mock-Ergebnis, ohne das Netzwerk zu berühren. Beide verändern die Datenbank nicht.

- [ ] **Schritt 6: Views** — In `core/views.py` ein gemeinsames `GoalAIActionMixin` mit `LoginRequiredMixin`, das in `post()`:
  1. das Goal per `get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)` auflöst — der 404 fällt also **vor** jedem API-Aufruf;
  2. die jeweilige Service-Funktion aufruft;
  3. das Ergebnis mit `goal_id` in die Session legt;
  4. bei `AIServiceError` `messages.error(request, str(fehler))` setzt;
  5. in beiden Fällen auf `goal.get_absolute_url()` zurückleitet (302).
  
  Daraus abgeleitet `GoalSummaryView` und `GoalNextStepsView`, die sich nur in Service-Funktion und Session-Schlüssel unterscheiden. Nur `post()` wird implementiert — ein GET läuft damit in 405 und löst keine Aktion aus.
  
  `GoalDetailView.get_context_data()` liest beide Session-Einträge und legt sie nur dann in den Kontext, wenn die hinterlegte `goal_id` zum aktuellen Goal passt.

- [ ] **Schritt 7: URLs** — `goals/<int:pk>/ai/summary/` → `goal_ai_summary` und `goals/<int:pk>/ai/next-steps/` → `goal_ai_next_steps`.

- [ ] **Schritt 8: Templates** — In `base.html` einen Messages-Block ergänzen (`{% if messages %}` mit `message.tags` als CSS-Klasse) sowie Styling für `.messages .error`. In `goal_detail.html` einen Abschnitt mit den beiden POST-Formularen (je `{% csrf_token %}`) und darunter die Ergebnisbereiche, jeweils in `{% if %}` gekapselt — vor der ersten Nutzung erscheint damit kein leerer Rumpf. Die nächsten Schritte werden als `<ol>` gerendert.

- [ ] **Schritt 9: Mock-Erzwingung in der Testsuite** — Damit kein Testlauf je das Netz berührt, auch nicht auf einem Entwicklerrechner mit gesetztem Key: Beide neuen Testmodule tragen `@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")` auf Klassenebene. Die Tests, die Fehlerpfade prüfen, patchen zusätzlich gezielt `_call_openai` und schalten den Mock dafür ab.

- [ ] **Schritt 10: Tests** — Die beiden Testmodule gemäß Abschnitt 4 schreiben.

- [ ] **Schritt 11: Gesamtvalidierung** — `manage.py check`, `makemigrations --check --dry-run`, `manage.py test` (90 bestehende plus neue) und `.\.workflow\hooks\validate_code.ps1`; alles mit Exit-Code 0. Zusätzlich eine Repository-Suche nach `sk-` als Nachweis, dass kein Schlüssel-Literal eingecheckt ist.

## 4. Validierung & Test-Strategie

### `core/tests/test_ai_service.py`

Mock-Modus:

- `test_mock_mode_active_without_api_key` — ohne Key ist `is_mock_mode()` wahr, auch wenn `AI_MOCK_MODE` aus ist.
- `test_mock_mode_active_when_explicitly_enabled`
- `test_generate_summary_returns_text_in_mock_mode` — nicht leer, enthält den Goal-Titel.
- `test_suggest_next_steps_returns_two_to_three_items` — Liste, Länge zwischen 2 und 3, alle Einträge nicht leer.
- `test_service_does_not_touch_database` — die Objektzahlen von `Goal`, `LearningSession` und `Resource` sind vor und nach beiden Aufrufen identisch.

Prompt-Inhalt (der sicherheitsrelevante Teil):

- `test_prompt_contains_only_own_goal_data` — zwei Nutzer mit je einem Goal, Sessions und Ressourcen mit eindeutigen Markertexten. Der Prompt für A's Goal enthält A's Marker und **keinen** Marker von B.
- `test_prompt_limits_number_of_sessions` — 25 Sessions anlegen, prüfen dass höchstens `MAX_SESSIONS` Datumsangaben im Prompt vorkommen.
- `test_prompt_contains_resources` — Ressourcentitel und -typ sind enthalten.

Fehler-Übersetzung (mit abgeschaltetem Mock und gepatchtem SDK):

- `test_timeout_is_translated_to_service_error` — `APITimeoutError` aus dem SDK → `AIServiceError`.
- `test_rate_limit_is_translated_to_service_error` — `RateLimitError` → `AIServiceError`.
- `test_unexpected_exception_is_translated_to_service_error` — ein beliebiger `RuntimeError` → `AIServiceError`.
- `test_error_message_does_not_leak_internals` — die Meldung enthält weder `"sk-"` noch `"Traceback"` noch den rohen Ausnahmetext.

### `core/tests/test_ai_views.py`

Alle Klassen mit `@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")`.

Kein Netzwerk:

- `test_no_external_call_during_tests` — `core.services.ai_service._call_openai` wird durch ein Double ersetzt, das bei jedem Aufruf `self.fail()` auslöst; danach werden beide Aktionen ausgeführt. Schlägt der Test nicht fehl, hat kein echter Aufruf stattgefunden.

Aktionen und Anzeige:

- `test_summary_action_redirects_to_goal_detail` — POST → 302 auf die Detailseite.
- `test_summary_result_visible_on_detail_page` — nach dem POST enthält die Detailseite den generierten Text.
- `test_next_steps_action_redirects_and_shows_list` — nach dem POST sind 2 bis 3 Listeneinträge im Kontext und im HTML.
- `test_actions_not_triggered_by_get` — GET auf beide URLs liefert 405 und legt nichts in die Session.
- `test_no_result_block_before_first_use` — die frische Detailseite enthält weder Zusammenfassungs- noch Next-Steps-Bereich.
- `test_result_of_other_goal_not_shown` — nach einer Zusammenfassung zu Goal 1 zeigt die Detailseite von Goal 2 (desselben Nutzers) diese **nicht** an.

Fehlerpfade (Mock abgeschaltet, Service-Funktion wirft `AIServiceError`):

- `test_timeout_shows_message_and_redirects` — 302, kein 500er, die Meldung erscheint nach dem Folge-GET in der Oberfläche.
- `test_rate_limit_shows_message`
- `test_unexpected_error_shows_message`
- `test_failed_action_leaves_no_result_in_session` — nach einem Fehler steht kein halbes Ergebnis in der Session.

Scoping:

- `test_ai_actions_require_login` — beide URLs, anonymer POST → `assertRedirects` auf die Login-Seite.
- `test_ai_actions_on_foreign_goal_return_404` — A postet auf beide Aktionen für B's Goal → 404.
- `test_foreign_goal_action_does_not_call_service` — zusätzlich belegt, dass dabei die Service-Funktion gar nicht erst aufgerufen wurde (Double zählt Aufrufe, erwartet 0). Der 404 fällt also vor dem API-Kontakt.
- `test_own_goal_actions_work` — Gegenprobe, damit die 404-Tests nicht durch eine global kaputte View trivial erfüllt sind.

### Testdaten

- `setUpTestData` legt Nutzer, Goals, Sessions und Ressourcen mit eindeutigen Markertexten an, damit Prompt-Inhalte eindeutig zuordenbar sind.
- Keine Fixture-Dateien. Kein Test benötigt einen API-Key oder Netzwerkzugang.

### Auszuführende Kommandos

```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

Zusätzlich als Sicherheitsnachweis:

```
git grep -n "sk-" -- . ":(exclude).venv"
```

### Definition of Done

Alle vier Kommandos enden mit Exit-Code 0, die 90 Tests aus Feature 1 bis 3 laufen unverändert mit durch, es entsteht **keine** neue Migration, die Repository-Suche nach einem Schlüssel-Literal bleibt ohne Treffer, und jedes der 31 Akzeptanzkriterien aus `.workflow/artifacts/ticket.md` ist durch mindestens einen benannten Test oder einen Kommando-Exit-Code belegt.

**Vorbehalt:** Der echte API-Pfad ist mangels Schlüssel in dieser Umgebung nicht end-to-end verifizierbar. Abgenommen werden Mock-Betrieb, Prompt-Aufbau und Fehlerbehandlung; die Korrektheit des SDK-Aufrufs gegen die Live-API bleibt offen und ist im Review als solche festzuhalten.
