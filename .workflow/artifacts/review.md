# Code Review: KI-Lernkarten-Generator mit interaktiver Abfrage

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, openai 1.109.1. **244 Tests** (205 Bestand + 39 neu), `ruff check .` ohne Befund, `makemigrations --check` sauber, `validate_code.ps1` Exit-Code 0.

> **Kostenschutz:** Kein Schritt dieses Durchlaufs hat die OpenAI-API erreicht. Tests laufen über den `OfflineTestRunner` bzw. mit gepatchtem SDK; die Sichtprüfung lief über eine zweite Server-Instanz mit `AI_MOCK_MODE=True` (die Umgebungsvariable hat Vorrang vor der `.env`).

---

## 1. Abdeckung der Akzeptanzkriterien

### Modell

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| `Flashcard` mit `goal` (FK, CASCADE), `question`, `answer`, `is_mastered` (default `False`), `created_at` | `core/models.py`, `related_name="flashcards"` | ja |
| Offene zuerst, darin neueste zuerst | `ordering = ["is_mastered", "-created_at", "-pk"]`; `test_offene_vor_gelernten_darin_neueste_zuerst` | ja |
| Besitzer nur über `goal__user` | kein `user`-Feld | ja |
| Migration `0005_flashcard`, additiv | `sqlmigrate`: ein `CREATE TABLE` + Index auf `goal_id`; angewendet | ja |
| Admin | `FlashcardAdmin` mit Liste, Filter, Suche | ja |

### Service

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| `generate_flashcards(goal)` liefert Dicts, schreibt nichts in die DB | einziger DB-Zugriff ist das Lesen vorhandener Fragen; gespeichert wird in der View | ja |
| Kontext = eigenes Goal; vorhandene Fragen gedeckelt im Prompt | `test_prompt_nur_mit_eigenen_goal_daten` (Notiz und Titel von B fehlen), `test_vorhandene_fragen_im_prompt` (Fragen anderer Goals fehlen); Deckel `MAX_EXISTING_QUESTIONS = 30` | ja |
| Structured Output `json_schema`, `strict: true`, `additionalProperties: false` auf jeder Ebene | `test_structured_output_mit_strict_schema` prüft das an den echten Aufrufparametern | ja |
| Konfiguriertes Modell (Standard `gpt-4o-mini`) | `test_konfiguriertes_modell` | ja |
| 3–5 im Code durchgesetzt | `test_zu_wenige_karten`, `test_zu_viele_karten_werden_gekuerzt` | ja |
| Fehlerfälle → `AIServiceError` + Log, nie 500 | `ParserTests`: ungültiges JSON, Liste statt Objekt, `cards` fehlt / kein Array, unvollständige Einträge verworfen, zu wenige; jeder Fehlerfall mit `assertLogs` | ja |
| Refusal | `test_refusal_wird_eigener_fehler` — eigene Meldung "abgelehnt", **nicht** in "nicht verfügbar" umgedeutet | ja |
| Duplikate in der Antwort und gegen Bestand verworfen | `test_duplikate_in_antwort_und_gegen_bestand` (Groß-/Kleinschreibung, Ränder), `test_nur_duplikate_ergeben_fehler` | ja |
| Mock: deterministisch 3 Karten | `test_drei_deterministische_karten_ohne_api` | ja |
| Text-Aktionen unverändert | `test_textaktionen_ohne_response_format`: Zusammenfassung sendet weiterhin kein `response_format` | ja |

### Aktion, Verwaltung, Anzeige

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Button in der KI-Card, nur POST | `test_nicht_per_get` (405, nichts gespeichert) | ja |
| Anhängen, Lernstatus bleibt; Redirect `#lernkarten`; Meldung im Abschnitt | `test_karten_werden_angehaengt_lernstatus_bleibt`, `test_meldung_im_abschnitt_genau_einmal` | ja |
| Fehler → nichts gespeichert, Meldung im Abschnitt | `test_fehler_speichert_nichts_meldung_im_abschnitt` (rot als `alert-danger`) | ja |
| Ladezustand wie die anderen KI-Buttons | dritter `data-ki-aktion`-Button, `data-ladetext="Erstelle Lernkarten..."`; das bestehende Script erfasst ihn ohne Änderung | ja |
| Umschalten / Löschen nur per POST | `VerwaltenViewTests` | ja |
| Akkordeon: Frage sichtbar, Antwort eingeklappt | `test_frage_im_kopf_antwort_eingeklappt` (`collapsed`, `aria-expanded="false"`, Antwort nicht im Kopf) | ja |
| Badge "Gelernt" mit Text, Fortschritt "x von y" | `test_gelernt_badge_und_fortschritt` (inkl. `aria-valuenow="50"`) | ja |
| Leerzustand | `test_leerzustand` | ja |
| Feste Abfrage-Anzahl | `test_abfragen_unabhaengig_von_kartenzahl` (2 vs. 8 Karten) | ja |

### Isolation und Sicherheit

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Login-Pflicht für alle drei Routen | `test_login_pflicht` (nichts geändert) | ja |
| Fremdes Goal → 404, Service nicht aufgerufen | `test_fremdes_goal_404_ohne_service_aufruf` | ja |
| Fremde Karte umschalten/löschen → 404 ohne Änderung | `test_fremde_karte_umschalten_und_loeschen_404`, Gegenprobe `test_gegenprobe_eigene_karte` | ja |
| Keine Karten fremder Goals in der Anzeige | `test_karten_anderer_goals_unsichtbar` | ja |
| KI-Text escaped | `test_ki_text_wird_escaped`: `<script>` und `<b>` aus Frage/Antwort erscheinen nur escaped | ja |
| CASCADE, Hinweis in der Goal-Löschbestätigung | `test_cascade_beim_goal_loeschen`; Text nennt Lernkarten | ja |

---

## 2. Gegenproben (Mutationen, jeweils zurückgesetzt)

| Mutation | Erkannt durch |
|---|---|
| Refusal wird in "nicht verfügbar" umgedeutet (`except AIServiceError: raise` entfernt) | `test_refusal_wird_eigener_fehler` |
| `response_format` wird nicht durchgereicht | `test_structured_output_mit_strict_schema` |
| Duplikate gegen den Bestand nicht geprüft | 3 Tests, inkl. Mock-Pfad |
| Mindestanzahl nicht durchgesetzt | `test_zu_wenige_karten`, `test_nur_duplikate_ergeben_fehler` |
| Umschalten/Löschen ohne `goal__user`-Filter | `test_fremde_karte_umschalten_und_loeschen_404` |
| Generieren speichert nicht | 2 Tests |
| Karten eines Durchlaufs in Einfügereihenfolge statt umgekehrt | `test_reihenfolge_der_ki_bleibt_neue_durchlaeufe_oben` |

Alle 7 Mutationen färben mindestens einen Test rot.

---

## 3. Befunde während der Umsetzung (alle behoben)

**1. Refusal hätte bestehende Tests gebrochen.** Die Service-Tests aus Feature 4 patchen das SDK mit `MagicMock`; dort ist `message.refusal` ein truthy Mock-Objekt. Eine naive Prüfung `if nachricht.refusal:` hätte jede gepatchte Antwort als Ablehnung gewertet. Lösung: Nur ein nicht-leerer **String** zählt als Ablehnung. Bestandstests unverändert grün.

**2. Reihenfolge innerhalb eines Durchlaufs war umgekehrt** (Sichtprüfung). `bulk_create` vergibt aufsteigende Zeitstempel, die Sortierung "neueste zuerst" kehrte die Reihenfolge der KI um — die Einstiegsfrage stand unten. `auto_now_add` überschreibt vorgegebene Zeitstempel, daher werden die Karten eines Durchlaufs in umgekehrter Reihenfolge angelegt; der `-pk`-Tiebreaker hält das auch bei identischen Zeitstempeln konsistent. Abgesichert durch einen Test über zwei Durchläufe.

**3. Der Mock-Modus umging den Duplikat-Schutz.** Ohne API-Schlüssel legte jeder Klick dieselben drei Beispielkarten erneut an — entgegen dem Ticket-Kriterium. Die Duplikat-Prüfung ist jetzt eine eigene Funktion `_ohne_duplikate`, die Parser und Mock gemeinsam nutzen. Im Browser bestätigt: Nach dem Löschen einer Karte liefert der nächste Klick genau diese eine zurück, ein weiterer Klick meldet "[Mock-Modus] Alle Beispiel-Lernkarten sind bereits vorhanden."

**4. "1 Lernkarten erstellt."** (Sichtprüfung) — Einzahl korrigiert, `test_meldung_in_der_einzahl`.

**5. Schlüsselartiges Literal aus Feature 8.** `test_ai_feedback.py` enthielt `"sk-test-…"` als Test-Schlüssel — ein Verstoß gegen die Konvention aus Feature 4, den ich in Feature 8 selbst eingeführt hatte. Ersetzt durch den Platzhalter der Konvention; `git grep "sk-"` über Code und Tests ist leer.

---

## 4. Code-Qualität

- **Mixin sauber verallgemeinert:** `GoalAIActionMixin` kennt nur noch Ablauf, Fehlerbehandlung, Meldungsort und Sprungziel; `AIFeedbackActionMixin` speichert in den Verlauf, `FlashcardGenerateView` als Lernkarten. Zusammenfassung und nächste Schritte verhalten sich unverändert — alle 205 Bestandstests liefen nach dem Refactoring vor dem ersten neuen Test grün.
- **Abschnitts-Meldungen vereinheitlicht:** statt einer Sonderregel pro Abschnitt ein Tag `abschnitt` plus Bereichsname und ein gemeinsames Partial `_abschnitt_meldungen.html`; der KI-Verlauf nutzt es ebenfalls. Fehler erscheinen dort jetzt korrekt rot (vorher kannte der Abschnitt nur Erfolgsmeldungen).
- **`_call_openai` minimal erweitert:** `response_format` wird nur gesetzt, wenn übergeben — die Text-Aufrufe sind byte-identisch, belegt durch `test_textaktionen_ohne_response_format`.
- **Schema bewusst ohne `minItems`/`maxItems`:** Ob der Strict-Modus diese Schlüsselwörter akzeptiert, ließ sich ohne kostenpflichtigen Aufruf nicht verifizieren; ein nicht unterstütztes Schlüsselwort hätte *jede* Anfrage scheitern lassen. Die Anzahl wird ohnehin im Code durchgesetzt.

---

## 5. Barrierefreiheit

- Akkordeon nach Bootstrap-Muster: `<button>` mit `aria-expanded`/`aria-controls`, Inhalt mit `aria-labelledby` auf die Frage; je Karte eindeutige IDs (`karte-<pk>`).
- Fragen als `<h3>` unter der Abschnittsüberschrift `<h2>` — per Überschriften-Navigation ansteuerbar.
- Umschalt- und Lösch-Buttons tragen einen visuell versteckten Kontext ("(Lernkarte: …)"); in der Button-Liste eines Screenreaders sind fünf "Als gelernt markieren" sonst nicht unterscheidbar.
- "Gelernt" als Text im Badge, nicht nur als Farbe; Fortschrittsbalken mit `role="progressbar"`, sprechendem `aria-label` und `aria-valuenow`.
- Erfolgs- und Fehlermeldungen im Abschnitt mit `role="status"` bzw. `role="alert"`; im Browser nach dem Sprung auf `#lernkarten` sichtbar gemessen.

---

## 6. Anpassung bestehender Tests

| Datei | Änderung | Grund |
|---|---|---|
| `test_ai_views.py` | `test_beide_formulare_…` → `test_alle_ki_formulare_…`: 3 statt 2 markierte KI-Formulare, dritter Ladetext | Die KI-Card bekommt laut Ticket einen dritten Button mit demselben Ladezustand. |
| `test_ai_feedback.py` | Test-Schlüssel-Literal ersetzt | Befund 5 |

---

## 7. Verifikation

```powershell
ruff check .                                        # All checks passed!
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test                               # Ran 244 tests — OK
.\.workflow\hooks\validate_code.ps1                 # Exit-Code 0
git grep "sk-" (Code und Tests)                     # keine Treffer
```

**Sichtprüfung** (Mock-Server, temporärer Prüfnutzer, anschließend samt Daten gelöscht): Generieren mit Spinner, Meldung im Abschnitt, Reihenfolge, Aufklappen, "Als gelernt markieren" mit Umsortierung und Fortschritt 1 von 3, Löschen, Neu-Generieren mit Duplikat-Schutz, Fehlermeldung im Abschnitt; 0 Konsolenfehler. Die Dev-Datenbank enthält danach wieder nur dein Konto mit deinen eigenen KI-Einträgen und 0 Lernkarten.

---

## 8. Fazit

Der Generator liefert strukturierte Lernkarten über Structured Outputs, validiert jede Antwort selbst und fängt alle Fehlerfälle — kaputtes JSON, falsche Struktur, zu wenige Karten, Duplikate, Ablehnung — mit verständlichen Meldungen ab. Die Abfrage-Ansicht ist zugänglich und mandantensicher; die Gegenproben belegen, dass die Tests die kritischen Stellen tatsächlich bewachen. Vier Mängel wurden in Umsetzung und Sichtprüfung gefunden und behoben, ein fünfter aus Feature 8 gleich mit.

**Freigabe erteilt: APPROVED.**
