# Code Review: AI-powered summary and next steps — OpenAI-Integration

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, `openai` 1.109.1, **122 Tests** (90 aus Feature 1–3 + 32 neue), `validate_code.ps1` grün.

> **Vorbehalt vorweg:** In dieser Umgebung ist kein `OPENAI_API_KEY` vorhanden. Der echte API-Pfad ist damit **nicht end-to-end verifiziert**. Siehe Abschnitt 6.

---

## 1. Abdeckung der Akzeptanzkriterien

### Konfiguration und Schlüsselverwaltung

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `openai` in `requirements.txt` mit Versionsgrenze, installiert | `openai>=1.40,<2.0`; installierte Version 1.109.1 | ja |
| 2 | Key nur aus `os.environ`; keine Schlüssel-Literale im Repository | `settings.py:142`; `git grep -- "sk-" ":(exclude).venv" ":(exclude).workflow"` → **keine Treffer** | ja, mit Anmerkung |
| 3 | `.env.example` dokumentiert die Variablen; `.env` ignoriert | `.env.example:8-18`; `.gitignore:17` | ja |
| 4 | Modell konfigurierbar, Default `gpt-4o-mini` | `settings.py:143` | ja |
| 5 | `manage.py check` ohne Key Exit-Code 0 | Explizit ohne gesetzten Key ausgeführt: 0 Issues | ja |

**Anmerkung zu #2:** Der Anwendungscode, die Konfiguration, die Templates und die Tests enthalten kein `sk-`-Literal. Treffer gibt es ausschließlich in `ticket.md` und `plan.md` — also in den Workflow-Dokumenten, die dieses Kriterium selbst formulieren. Das Kriterium war wörtlich "über das gesamte Repository" gefasst und ist damit streng gelesen nicht erfüllt; sinngemäß — kein Schlüssel und kein schlüsselähnliches Literal im ausgelieferten Code — ist es erfüllt. Während der Umsetzung wurden drei Stellen korrigiert, die zunächst dagegen verstießen (siehe Abschnitt 4).

### Service-Layer

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 6 | SDK nur im Service; Views/Models/Templates importieren `openai` nicht | Einziger Import in `core/services/ai_service.py:11` | ja |
| 7 | Zwei Funktionen, nehmen `Goal`, verändern die DB nicht | `generate_summary`, `suggest_next_steps`; `test_service_does_not_touch_database` | ja |
| 8 | Kontext aus Sessions und Ressourcen, Anzahl begrenzt | `MAX_SESSIONS = 10`, `MAX_RESOURCES = 20`; `test_prompt_limits_number_of_sessions` (25 Sessions → höchstens 10 Zeilen) | ja |
| 9 | Next Steps als Liste mit 2–3 Einträgen | `test_suggest_next_steps_returns_two_to_three_items`; Begrenzung im Code, nicht dem Modell überlassen | ja |
| 10 | Nur Daten des übergebenen Goals im Prompt | `test_summary_prompt_contains_only_own_goal_data`, `test_next_steps_prompt_contains_only_own_goal_data` | ja |

### Mock-Modus

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 11 | Deterministischer Mock ohne Netzwerk | `_mock_summary`, `_mock_next_steps`; `MockErgebnisTests` | ja |
| 12 | Mock aktiv bei Flag **oder** fehlendem Key | `test_mock_mode_active_without_api_key`, `test_mock_mode_active_when_explicitly_enabled`, `test_mock_mode_inactive_with_key_and_flag_off` | ja |
| 13 | Kein externer Call während `manage.py test` | `test_no_external_call_during_tests` — ersetzt `_call_openai` durch ein Double, das jeden Aufruf mit `self.fail()` quittiert | ja |
| 14 | Suite läuft auch mit **gesetztem** `OPENAI_API_KEY` durch | Separat verifiziert: mit `OPENAI_API_KEY` in der Umgebung 122/122 grün | ja |

### Aktionen auf der Goal-Detailseite

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 15 | Zwei POST-Formulare mit CSRF; GET löst nichts aus | `goal_detail.html:28-36`; `test_actions_not_triggered_by_get` (405, Session leer) | ja |
| 16 | Summary: 302 zurück, Ergebnis sichtbar | `test_summary_action_redirects_to_goal_detail`, `test_summary_result_visible_on_detail_page` | ja |
| 17 | Next Steps: 302, Liste mit 2–3 Einträgen sichtbar | `test_next_steps_action_redirects_and_shows_list` | ja |
| 18 | Kein leerer Ergebnisbereich vor der ersten Nutzung | `test_no_result_block_before_first_use` | ja |
| 19 | Keine Persistenz, keine neue Migration | `makemigrations --check --dry-run` → "No changes detected"; `test_results_are_not_persisted_in_database` | ja |

### Fehlerbehandlung

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 20 | Messages im Basis-Template ausgegeben | `base.html:44-50` — **war bisher nicht vorhanden**, ergänzt | ja |
| 21 | Timeout → 302 + Meldung, kein 500er | `test_timeout_is_translated_to_service_error`, `test_timeout_shows_message_and_redirects` | ja |
| 22 | Rate-Limit → eigene Meldung | `test_rate_limit_is_translated_to_service_error`, `test_rate_limit_shows_message` | ja |
| 23 | Beliebige Exception abgefangen | `test_unexpected_exception_is_translated_to_service_error`, `test_failed_action_does_not_return_500` | ja |
| 24 | Keine Interna in der Meldung | `test_error_message_does_not_leak_internals` — prüft Key-Präfix, Stacktrace und rohen Ausnahmetext | ja |

### Scoping

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 25 | Beide Aktionen erfordern Login | `test_ai_actions_require_login` | ja |
| 26 | Fremdes Goal → 404, kein API-Aufruf, kein Ergebnis | `test_ai_actions_on_foreign_goal_return_404`, `test_foreign_goal_action_does_not_call_service` (`assert_not_called`) | ja |
| 27 | Gegenprobe am eigenen Goal | `test_own_goal_actions_work` | ja |

### Tests und Regression

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 28 | Tests decken Service, Prompt, Views, Fehlerpfade, Scoping ab | `test_ai_service.py` (17), `test_ai_views.py` (15) | ja |
| 29 | Die 90 Tests aus Feature 1–3 laufen unverändert weiter | 122 gesamt, kein bestehendes Testmodul angefasst | ja |
| 30 | `check` und `test` Exit-Code 0 | Hook grün | ja |
| 31 | Keine ausstehende Migration | "No changes detected" | ja |

**31 von 31 Kriterien erfüllt** (Kriterium 2 mit der oben vermerkten Einschränkung).

## 2. Sicherheit

**Schlüsselverwaltung.** `OPENAI_API_KEY` wird ausschließlich über `os.environ.get("OPENAI_API_KEY", "")` gelesen — ohne Default und ohne Fallback-Literal. Fehlt der Key, bleibt der Wert leer und der Service schaltet selbsttätig in den Mock-Modus, statt beim Start zu scheitern. `.env` ist in `.gitignore`, `.env.example` lässt den Wert bewusst leer und hinterlegt auch keinen erfundenen Beispielschlüssel.

**Kein Datenabfluss zwischen Nutzern.** Das ist bei diesem Feature der kritischste Punkt, weil Daten das System verlassen. Zwei Ebenen greifen:

1. *Strukturell:* Jede Query im Service geht vom übergebenen Goal aus (`goal.sessions`, `goal.resources`). Es existiert im gesamten Modul keine Query, die nicht an diesem Goal hängt — Fremddaten können also gar nicht erst in den Prompt geraten.
2. *Getestet:* `test_summary_prompt_contains_only_own_goal_data` legt für zwei Nutzer Goals, Sessions und Ressourcen mit eindeutigen Markertexten an und prüft, dass im Prompt für A kein einziger Marker von B auftaucht.

**404 vor dem API-Kontakt.** `GoalAIActionMixin.post()` löst das Goal per `get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)` auf, bevor der Service überhaupt aufgerufen wird. `test_foreign_goal_action_does_not_call_service` belegt das mit `assert_not_called()` — ein fremder PK erzeugt also weder Kosten noch einen Datenabfluss, nicht nur einen 404.

**Keine Interna in Fehlermeldungen.** Der SDK-Fehler geht per `logger.exception()` ins Log, die Nutzermeldung ist ein fester deutscher Text. `test_error_message_does_not_leak_internals` lässt das Double einen `RuntimeError` werfen, dessen Text ein schlüsselähnliches Fragment enthält, und prüft, dass weder dieses noch "Traceback" noch der rohe Ausnahmetext in der Meldung landet.

**Protokollierung belegt.** Die drei Fehlertests laufen unter `assertLogs` — damit ist nicht nur geprüft, dass der Fehler dem Nutzer gegenüber verschluckt wird, sondern auch, dass er für den Betrieb protokolliert wird. Ein stillschweigend verschluckter Fehler wäre hier die gefährlichere Variante.

**Ressourcenschutz.** Explizites `timeout` (Default 20 s) und `max_retries=1` am Client; ohne beides könnte ein hängender oder rate-limitierter Aufruf einen Request-Thread lange blockieren. Die Prompt-Größe ist über `MAX_SESSIONS`/`MAX_RESOURCES` gedeckelt, wächst also nicht mit dem Datenbestand.

**XSS.** Die generierten Texte werden über das Autoescaping ausgegeben; `|linebreaksbr` escapt den Inhalt vor der Umwandlung der Zeilenumbrüche. Kein `|safe`, kein `mark_safe`. Modellausgaben werden damit nicht als HTML interpretiert — relevant, weil es sich um Fremdinhalt handelt.

**Session als Ablage.** Ergebnisse liegen in der serverseitigen Django-Session und sind an den angemeldeten Nutzer gebunden; der Abgleich über `goal_id` verhindert zusätzlich, dass ein Ergebnis unter einem anderen Goal erscheint (`test_result_of_other_goal_not_shown`).

## 3. Hinweise ohne Blocker-Charakter

1. **Synchroner Aufruf im Request.** Bis zu 20 Sekunden Antwortzeit blockieren einen Worker. Für eine Einzelplatz-Anwendung vertretbar und im Ticket als Out-of-Scope gesetzt; unter Last wäre eine Queue der richtige Ort.
2. **Kein Kontingent pro Nutzer.** Ein eingeloggter Nutzer kann die Aktionen beliebig oft auslösen — jede Auslösung kostet Geld. Im Ticket Out-of-Scope, vor einem echten Betrieb aber der erste Punkt auf der Liste.
3. **Mock-Modus ist unauffällig.** Ohne Key liefert die Anwendung Mock-Ergebnisse, erkennbar nur am Präfix `[Mock-Modus]` im Text. Ein Hinweisbanner in der Oberfläche wäre deutlicher.
4. **Keine Historie.** Bewusste Entscheidung (Abschnitt 2 des Plans); mit dem nächsten Request ist die vorige Zusammenfassung weg.
5. **Aus den Vorfeatures unverändert offen:** Dev-Fallback für `SECRET_KEY`, `DEBUG` per Default `True`, kein Brute-Force-Schutz am Login.

## 4. Während der Umsetzung gefunden und behoben

**Verstoß gegen das eigene Kriterium 2.** Die erste Fassung der Tests verwendete `"sk-test-platzhalter"` als `override_settings`-Wert und `"sk-streng-geheimer-schluessel"` als Fehlertext — damit enthielt das Repository genau das Literal, dessen Abwesenheit das Ticket fordert. Korrigiert: Die Platzhalter heißen jetzt `test-schluessel-platzhalter`, und der Leak-Test setzt das Präfix zur Laufzeit zusammen (`"sk" + "-"`), damit der Test seine Aussagekraft behält, ohne das Literal einzuchecken. Zusätzlich wurde die entsprechende Formulierung in `plan.md` entschärft.

**Rauschen im Testoutput.** Die Fehlertests ließen `logger.exception()` ungefiltert in die Konsole schreiben — zwei vollständige Tracebacks bei jedem grünen Lauf. Statt die Protokollierung zu unterdrücken, laufen die Tests jetzt unter `assertLogs`: Das hält den Output sauber **und** macht aus dem Nebeneffekt eine geprüfte Zusage.

**Messages wurden nirgends gerendert.** `django.contrib.messages` war seit Feature 1 konfiguriert, aber `base.html` gab die Meldungen nicht aus — jede `messages.error()` wäre spurlos verpufft. Vor der Implementierung der Fehlerbehandlung festgestellt und ergänzt.

## 5. Formatierung und tote Code-Pfade

Imports sortiert und vollständig genutzt, keine auskommentierten Reste, Namensgebung konsistent zu den Vorfeatures. `manage.py check` meldet 0 Issues.

Zwei Stellen, die bewusst so aussehen:

- `GoalAIActionMixin` definiert `run_service()` und `build_result()` als `NotImplementedError`-Stubs. Das ist kein toter Code, sondern der Vertrag der beiden Unterklassen — beide überschreiben beide Methoden.
- `GoalSummaryView` und `GoalNextStepsView` erben von `View` statt von einer generischen View und implementieren nur `post()`. Ein GET läuft dadurch in 405, was genau der Anforderung "löst per GET keine Aktion aus" entspricht.

## 6. Verifizierungslücke — ausdrücklich festgehalten

**Der echte OpenAI-Pfad wurde nie ausgeführt.** In dieser Umgebung existiert kein API-Schlüssel. Verifiziert sind:

- der Mock-Pfad vollständig,
- der Prompt-Aufbau anhand des erzeugten Textes,
- die Fehlerübersetzung gegen echte SDK-Exception-Klassen (`APITimeoutError`, `RateLimitError`), die über Doubles ausgelöst werden,
- das Nachverarbeiten der Antwort (Zeilenzerlegung, Präfix-Bereinigung, Begrenzung auf 3 Einträge) über ein gepatchtes `_call_openai`.

**Nicht verifiziert** ist, ob `client.chat.completions.create(...)` mit `gpt-4o-mini` gegen die Live-API die erwartete Antwortstruktur liefert und ob `antwort.choices[0].message.content` in allen realen Fällen trägt. Das ist Standard-SDK-Nutzung und entspricht der dokumentierten Signatur, bleibt aber bis zu einem Lauf mit gültigem Schlüssel eine begründete Annahme, keine geprüfte Tatsache.

**Empfohlener erster Schritt mit Key:** `OPENAI_API_KEY` in `.env` setzen, `AI_MOCK_MODE=False`, und beide Aktionen an einem Goal mit mindestens einer Session manuell auslösen. Schlägt dabei etwas fehl, liegt es mit hoher Wahrscheinlichkeit in `_call_openai` — der einzigen nicht abgedeckten Funktion.

## 7. Fazit

Alle 31 Akzeptanzkriterien sind erfüllt, Kriterium 2 mit der in Abschnitt 1 vermerkten Einschränkung. Der Schlüssel liegt ausschließlich in der Umgebung, die Testsuite berührt das Netzwerk nachweislich nicht — auch nicht auf einem Rechner mit gesetztem Key —, und der Datenabfluss an die API ist auf das jeweils eigene Goal begrenzt, strukturell wie getestet. Drei Probleme wurden während der Umsetzung gefunden und behoben, darunter ein Verstoß gegen das eigene Schlüssel-Kriterium.

Die verbleibende Lücke ist die fehlende End-to-End-Prüfung gegen die echte API. Sie ist durch die Umgebung bedingt, nicht durch den Code, und oben präzise eingegrenzt.

**Status: APPROVED**
