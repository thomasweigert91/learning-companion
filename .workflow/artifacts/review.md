# Code Review: Persistente KI-Historie zu Lernzielen (+ Vorab: .env-Unterstützung)

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, python-dotenv 1.2.4. **199 Tests** (175 Bestand + 1 Schutztest + 23 neu), `ruff check .` ohne Befund, `makemigrations --check` sauber, `validate_code.ps1` Exit-Code 0.

> **Kostenschutz während des gesamten Durchlaufs:** Der Dev-Server lief mit echtem OpenAI-Schlüssel. Weder Tests noch Sichtprüfung haben die API erreicht: Tests laufen über den neuen `OfflineTestRunner`, die Sichtprüfung nutzte direkt angelegte Datenbank-Einträge und hat keinen KI-Button ausgelöst.

---

## 1. Vorab-Aufgabe: `.env` per python-dotenv

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| `python-dotenv` mit Versionsgrenze | `requirements.txt`: `python-dotenv>=1.0,<2.0`, installiert 1.2.4 | ja |
| `.env` wird vor allen Einstellungen geladen | `load_dotenv(BASE_DIR / ".env")` direkt nach `BASE_DIR`; frischer `manage.py shell`-Prozess ohne manuell gesetzte Variable → Schlüssel geladen, `is_mock_mode() == False` | ja |
| Echte Umgebung hat Vorrang | `override=False` (Default) — Container und CI lesen weiter ihre echten Variablen; eine `.env` existiert dort nicht (`.dockerignore`, nicht versioniert) | ja |
| Tests erreichen nie das echte Konto | `OfflineTestRunner` erzwingt `AI_MOCK_MODE=True` und leeren Schlüssel; `test_testlauf_erzwingt_mock_modus` | ja |

**Warum der Test-Runner nötig ist — belegt, nicht angenommen:** Derselbe Schutztest mit Djangos Standard-Runner (`--testrunner django.test.runner.DiscoverRunner`) **schlägt fehl** (`AssertionError: False is not true`), weil die `.env` den echten Schlüssel in die Test-Settings bringt. Die bestehenden KI-Tests überschreiben den Schlüssel zwar einzeln, aber jeder künftige Test ohne diese Überschreibung hätte echte, kostenpflichtige Aufrufe ausgelöst. Tests, die den Nicht-Mock-Pfad prüfen, überschreiben den globalen Schutz weiterhin gezielt und patchen dabei das SDK.

---

## 2. Feature 8: Abdeckung der Akzeptanzkriterien

### Modell

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `AIFeedback` mit `goal` (FK, CASCADE), `feedback_type`, `content`, `created_at` | `core/models.py`; Felder exakt wie spezifiziert, `related_name="ai_feedbacks"` | ja |
| 2 | Neueste zuerst, `-pk` als Tiebreaker | `test_sortierung_neueste_zuerst`, `test_gleicher_zeitstempel_nach_pk` | ja |
| 3 | Schritte zeilenweise, `steps`-Property | `test_steps_aus_zeilen` (Leerzeilen und Ränder bereinigt), `test_next_steps_zeilenweise_gespeichert` (Rundreise Liste → DB → Liste) | ja |
| 4 | Besitzer nur über `goal__user` | kein `user`-Feld; alle Abfragen gehen vom gescopten Goal oder von `goal__user` aus | ja |
| 5 | Migration `0004_aifeedback` erzeugt und angewendet | `sqlmigrate`: ein `CREATE TABLE` + Index auf `goal_id`, keine bestehende Tabelle berührt; auf die Dev-DB angewendet | ja |
| 6 | Admin-Registrierung | `AIFeedbackAdmin` mit Liste, Filter nach Typ, Suche | ja |

### Speichern

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 7 | Genau ein Eintrag pro erfolgreicher Aktion, richtiger Typ | `test_summary_wird_gespeichert`, `test_next_steps_zeilenweise_gespeichert`, `test_results_are_persisted_per_type` | ja |
| 8 | Historie statt Überschreiben | `test_jede_aktion_ein_neuer_eintrag` (2 Aufrufe → 2 Einträge) | ja |
| 9 | Fehler → nichts gespeichert | `test_fehler_speichert_nichts` (beide Aktionen), `test_failed_action_leaves_no_result` | ja |
| 10 | Echter Pfad speichert die Modellantwort | `test_echter_pfad_speichert_modellantwort`: Mock aus, `_call_openai` gepatcht, gespeichert wird die bereinigte Antwort | ja |
| 11 | Session-Speicher vollständig entfernt | `AI_SUMMARY_KEY`/`AI_NEXT_STEPS_KEY` und alle `request.session`-Zugriffe der KI-Views entfernt; `grep` in Code und Tests ohne Treffer | ja |
| 12 | `ai_service` bleibt datenbankfrei | Datei unverändert; `test_service_does_not_touch_database` grün; gespeichert wird in `GoalAIActionMixin.post` | ja |
| 13 | Auch Mock-Ergebnisse werden gespeichert | Mock-Text trägt bereits "[Mock-Modus]" und ist in der Historie als solcher erkennbar | ja |

### Anzeige

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 14 | KI-Card zeigt neuestes Ergebnis je Typ, mit Datum | `test_neuestes_ergebnis_in_ki_card` (ältere Einschätzung erscheint nicht in der Card); im Browser: nach Löschen des neuesten Eintrags fällt die Card korrekt auf den nächstälteren zurück | ja |
| 15 | Timeline `#ki-verlauf`: Datum (`<time datetime>`), Typ-Badge, formatierter Text, neueste zuerst | `test_timeline_zeigt_alle_eintraege`; Screenshot begutachtet | ja |
| 16 | Leerzustand | `test_leerzustand` (Hinweis da, "Alle zuruecksetzen" nicht) | ja |
| 17 | Keine N+1-Abfragen | **eine** Abfrage für die gesamte Historie; das Neueste je Typ wird aus derselben Liste gewählt; `test_abfragen_unabhaengig_von_eintragszahl` (2 vs. 8 Einträge, gleiche Query-Zahl) | ja |
| 18 | Keine Einträge fremder Goals | `test_eintraege_anderer_goals_unsichtbar` | ja |

### Löschen

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 19 | Einzel-Löschen per POST, Redirect auf `#ki-verlauf`, Meldung | `test_einzelnen_eintrag_loeschen`; im Browser durchgeklickt | ja |
| 20 | "Alle zurücksetzen": GET bestätigt, POST löscht nur dieses Goal | `test_alle_zuruecksetzen_bestaetigung` (GET löscht nichts), `test_alle_zuruecksetzen_betrifft_nur_dieses_goal` | ja |
| 21 | Login-Pflicht, 404 für Fremdes **ohne** Löschung, GET → 405 | `ScopingTests` (4 Fälle inkl. Gegenprobe), `test_einzel_loeschen_nicht_per_get` | ja |
| 22 | CASCADE beim Goal-Löschen, Hinweis in der Bestätigung | `test_cascade_beim_goal_loeschen`; Text nennt jetzt Lernsitzungen, Ressourcen und KI-Verlauf | ja |

---

## 3. Sicherheit

**Mandantentrennung — per Mutation geprüft:**

| Mutation (danach zurückgesetzt) | Ergebnis |
|---|---|
| `AIFeedback.objects.create(...)` entfernt | 8 Tests rot (Speichern, Anzeige, Scoping-Gegenprobe) |
| Einzel-Löschen ohne `goal__user`-Filter | `test_fremder_eintrag_404_ohne_loeschung` rot |
| "Zurücksetzen" löscht alle Einträge des Nutzers statt des Goals | `test_alle_zuruecksetzen_betrifft_nur_dieses_goal` rot |

Beide Lösch-Views folgen dem Projektmuster "gefiltert statt nachträglich geprüft": Ein fremder PK ist im Queryset nicht enthalten, die 404 fällt, bevor irgendetwas gelöscht wird.

**XSS durch KI-Ausgaben:** Modellantworten sind nicht vertrauenswürdige Eingaben — ein Prompt-Injection-Versuch in Notizen oder Ressourcen-Titeln könnte HTML in der Antwort provozieren. Ausgegeben wird ausschließlich über `|linebreaksbr` (escaped vor dem Umbruch) bzw. `{{ schritt }}` (Autoescape). Kein `|safe` im neuen Code.

**CSRF / Methoden:** Beide Lösch-Aktionen sind POST mit `{% csrf_token %}`; GET auf die Einzel-Löschroute → 405, GET auf "Zurücksetzen" zeigt nur die Bestätigung.

**Secrets:** `.env` bleibt durch `.gitignore` und `.dockerignore` außerhalb von Repository und Image. Der Testlauf ist vom echten Konto getrennt (Abschnitt 1).

---

## 4. Befund der Sichtprüfung: Erfolgsmeldung außerhalb des Sichtbereichs

**Gefunden:** Nach dem Löschen leitet die View auf `#ki-verlauf` um, damit man an der Stelle bleibt, an der man gearbeitet hat. Die Erfolgsmeldung erschien aber im globalen Meldungsbereich oben auf der Seite — im Browser gemessen **671 px oberhalb des sichtbaren Bereichs**. Wer löscht, sah keine Bestätigung.

**Behoben:** Meldungen der KI-Historie tragen `extra_tags="ki-verlauf"`. `base.html` überspringt sie, `_ai_timeline.html` zeigt sie direkt im Abschnitt an. Nachgemessen: Meldung sichtbar (509 px im Viewport), genau **eine** Meldung auf der Seite. Abgesichert durch `test_meldung_erscheint_im_verlauf_statt_oben` (genau ein Vorkommen, und zwar nach `id="ki-verlauf"`).

---

## 5. Barrierefreiheit

- Timeline als `<ol>`: die Reihenfolge ist Teil der Information und wird Screenreadern als Liste mit Anzahl angesagt.
- Zeitpunkte als `<time datetime="…">` in maschinenlesbarem ISO-Format.
- Typ nie nur über Farbe: Badge mit Icon **und** Text; Timeline-Punkte sind reine Zierde.
- Lösch-Buttons mit sprechendem `aria-label` ("KI-Eintrag (Zusammenfassung) vom 01.10.2026 13:06 loeschen") — in einer Liste gleicher Icons sonst nicht unterscheidbar.
- Lösch-Button bewusst als `btn-sm btn-outline-danger` statt als nackter Icon-Link mit `p-0`: Letzterer hätte die Mindest-Zielgröße von 24×24 px (WCAG 2.5.8) unterschritten.
- Abschnitt mit `aria-labelledby`; Erfolgsmeldung mit `role="status"`.

---

## 6. Anpassung bestehender Tests

Ein Bestandsmodul wurde geändert: `core/tests/test_ai_views.py` (+23/−12). Grund ist die im Ticket festgehaltene **Vertragsumkehr** — Feature 4 hat per Test festgeschrieben, dass Ergebnisse nur in der Session und nie in der Datenbank liegen. Die Absicht jedes Tests bleibt erhalten, nur das Speichermedium wechselt:

| Test | Änderung |
|---|---|
| `test_actions_not_triggered_by_get` | Session-Schlüssel → `AIFeedback.objects.count() == 0` |
| `test_results_are_not_persisted_in_database` | ersetzt durch `test_results_are_persisted_per_type` (Gegenteil, wie vom Ticket gefordert) |
| `test_failed_action_leaves_no_result_in_session` | → `test_failed_action_leaves_no_result`, prüft die DB |
| `test_own_goal_actions_work` | Session-Schlüssel → je ein Eintrag pro Typ |
| `test_next_steps_action_redirects_and_shows_list` | `context["ai_next_steps"]` → `.steps` |

Kein Test wurde abgeschwächt; alle übrigen Bestandsmodule sind unverändert.

---

## 7. Abweichungen gegenüber dem Plan

| Abweichung | Bewertung |
|---|---|
| `extra_tags="ki-verlauf"` und Meldungsanzeige im Abschnitt | Fix aus der Sichtprüfung, Abschnitt 4. |
| Lösch-Button als Outline-Button statt Icon-Link | Zielgröße, Abschnitt 5. |
| 23 statt 22 neue Tests | zusätzlich `test_gleicher_zeitstempel_nach_pk`, `test_eigene_loeschung_funktioniert` (Gegenprobe) und `test_meldung_erscheint_im_verlauf_statt_oben`. |
| Link "Zum KI-Verlauf (n)" im Fuß der KI-Card | Die Timeline steht am Ende der Hauptspalte; der Link verbindet die Card mit dem Verlauf. Additiv. |

---

## 8. Hinweis für den Betrieb

`python-dotenv` ist eine neue Laufzeit-Abhängigkeit und wird von `settings.py` importiert. Ein vorhandenes, älteres Docker-Image muss daher **neu gebaut** werden (`docker compose build`), sonst startet es mit `ModuleNotFoundError`. Die CI baut das Image bei jedem Lauf neu und deckt das ab.

---

## 9. Verifikation

```powershell
ruff check .                                        # All checks passed!
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test                               # Ran 199 tests — OK
.\.workflow\hooks\validate_code.ps1                 # Exit-Code 0
```

**Sichtprüfung** mit temporärem Prüfnutzer und direkt angelegten Einträgen (keine API-Aufrufe): Timeline mit vier Einträgen, Einzel-Löschen mit Rückfall der KI-Card, Bestätigungsseite, "Alle zurücksetzen", Leerzustand; 0 Konsolenfehler. Prüfnutzer samt Daten anschließend gelöscht — in der Dev-Datenbank sind nur dein Konto, 0 KI-Einträge und 0 Tags.

---

## 10. Fazit

KI-Ergebnisse überleben jetzt Logout und Browserwechsel, bilden eine nachvollziehbare Historie und lassen sich einzeln oder gesamt löschen — streng auf den Besitzer begrenzt, wie die Mutationsproben belegen. Die `.env`-Unterstützung macht den lokalen Start bequem, ohne die Testsuite an das echte, kostenpflichtige Konto zu koppeln. Ein Bedienfehler (unsichtbare Erfolgsmeldung) wurde in der Sichtprüfung gefunden und behoben.

**Freigabe erteilt: APPROVED.**
