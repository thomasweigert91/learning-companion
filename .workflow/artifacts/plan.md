# Implementierungs-Plan: KI-Lernkarten-Generator mit interaktiver Abfrage

## 1. Betroffene Dateien

- Ändern: `core/models.py` (Modell `Flashcard`)
- Neu: `core/migrations/0005_flashcard.py` (per `makemigrations`)
- Ändern: `core/admin.py` (Registrierung `Flashcard`)
- Ändern: `core/services/ai_service.py` (`generate_flashcards`, Schema, Parser, Mock; `_call_openai` um `response_format` und Refusal-Prüfung erweitert)
- Ändern: `core/views.py` (Mixin um Speicher-Hook verallgemeinert; drei neue Views; Kontext der Detailseite; einheitliche Abschnitts-Meldungen)
- Ändern: `core/urls.py` (drei Routen)
- Ändern: `core/templates/core/goal_detail.html` (dritter KI-Button, Abschnitt "Lernkarten")
- Neu: `core/templates/core/_flashcards.html` (Akkordeon-Partial)
- Neu: `core/templates/core/_abschnitt_meldungen.html` (Meldungen innerhalb eines Abschnitts)
- Ändern: `core/templates/core/_ai_timeline.html` (nutzt das neue Meldungs-Partial)
- Ändern: `core/templates/base.html` (überspringt Abschnitts-Meldungen generisch)
- Ändern: `core/templates/core/goal_confirm_delete.html` (Hinweis auf Lernkarten)
- Ändern: `core/tests/test_ai_views.py` (Ladezustand: drei statt zwei KI-Formulare)
- Ändern: `core/tests/test_ai_feedback.py` (schlüsselartiges Test-Literal ersetzt, siehe unten)
- Neu: `core/tests/test_flashcards.py`

**Vorab behoben:** `test_ai_feedback.py` enthielt seit Feature 8 das Literal
`"sk-test-…"` als Test-Schlüssel. Das verstößt gegen die Projektkonvention aus
Feature 4 (kein schlüsselartiges Literal im Repository, siehe
`TEST_SCHLUESSEL` in `test_ai_service.py`) und würde von Secret-Scannern
gemeldet. Ersetzt durch den Platzhalter der Konvention.

## 2. Datenmodelle & Migrationen

```python
class Flashcard(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="flashcards")
    question = models.TextField()
    answer = models.TextField()
    is_mastered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Abfrage-Reihenfolge: offene Karten zuerst (False < True), darin neueste zuerst.
        ordering = ["is_mastered", "-created_at", "-pk"]
```

- Kein `user`-Feld; Besitz über `goal__user` wie bei `LearningSession`,
  `Resource`, `AIFeedback`.
- Migration `0005_flashcard`: ein `CREATE TABLE` plus Index auf `goal_id`,
  keine bestehende Tabelle berührt.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Setup & Models** -- Modell, Migration erzeugen und
      anwenden, Admin (`list_display = ("question", "goal", "is_mastered", "created_at")`,
      `list_filter = ("is_mastered",)`).

- [ ] **Schritt 2: Service**

      *Konstanten:* `MIN_FLASHCARDS = 3`, `MAX_FLASHCARDS = 5`,
      `MAX_EXISTING_QUESTIONS = 30` (Deckel für die Duplikat-Liste im Prompt).

      *Schema* (Strict Structured Output):
      ```python
      FLASHCARD_RESPONSE_FORMAT = {
          "type": "json_schema",
          "json_schema": {
              "name": "lernkarten",
              "strict": True,
              "schema": {
                  "type": "object",
                  "properties": {
                      "cards": {
                          "type": "array",
                          "items": {
                              "type": "object",
                              "properties": {
                                  "question": {"type": "string"},
                                  "answer": {"type": "string"},
                              },
                              "required": ["question", "answer"],
                              "additionalProperties": False,
                          },
                      }
                  },
                  "required": ["cards"],
                  "additionalProperties": False,
              },
          },
      }
      ```
      Strict-Modus verlangt `required` für alle Felder und
      `additionalProperties: false` auf jeder Objektebene -- beides erfüllt.
      Keine `minItems`/`maxItems` (siehe Ticket, Rahmenbedingungen).

      *`_call_openai(prompt, response_format=None)`:* reicht `response_format`
      nur durch, wenn gesetzt -- die beiden bestehenden Aufrufe bleiben
      byte-identisch. Neu: Liefert das Modell eine `refusal`, wird eine
      `AIServiceError` geworfen. Damit sie nicht vom generischen
      `except Exception` in "nicht verfügbar" umgedeutet wird, steht davor ein
      `except AIServiceError: raise`.

      *`_build_flashcards_prompt(goal, vorhandene_fragen)`:* Aufgabe (3–5
      Paare auf Deutsch, aus dem Kontext beantwortbar, knappe Antworten), dann
      `_format_context(goal)`, dann ggf. "Diese Fragen existieren bereits …".

      *`_parse_flashcards(rohtext, vorhandene_fragen)`:*
      1. `json.loads` → bei `JSONDecodeError` loggen + `AIServiceError`.
      2. Kein `dict` oder `cards` keine Liste → loggen + `AIServiceError`.
      3. Je Eintrag: nur `dict` mit nicht-leerem `str` in beiden Feldern;
         `strip()`; Duplikat-Schlüssel `frage.strip().casefold()` gegen bereits
         Gesehenes und Vorhandenes.
      4. Weniger als `MIN_FLASHCARDS` → `AIServiceError`;
         mehr als `MAX_FLASHCARDS` → kürzen.

      *`generate_flashcards(goal)`:* vorhandene Fragen (gedeckelt) laden;
      im Mock `_mock_flashcards(goal)`, sonst Prompt → `_call_openai(…,
      FLASHCARD_RESPONSE_FORMAT)` → Parser. Rückgabe: Liste von Dicts. Keine
      DB-Schreibzugriffe.

      *`_mock_flashcards(goal)`:* drei Karten aus Titel, Sitzungszahl/-minuten
      und Ressourcenzahl -- deterministisch, mit "[Mock-Modus]" markiert.

- [ ] **Schritt 3: Views**

      *Mixin verallgemeinern:* `GoalAIActionMixin.post` ruft nach Erfolg
      `self.save_result(goal, ergebnis)` und danach `self.success_response(goal, anzahl)`.
      Für Zusammenfassung/Schritte bleibt das Verhalten identisch (AIFeedback
      anlegen, Redirect auf die Detailseite, Fehler oben). Neue Klassenattribute
      `error_extra_tags` und `anchor` steuern Meldungsort und Sprungziel.

      `FlashcardGenerateView`: `run_service` → `generate_flashcards`;
      `save_result` → `Flashcard.objects.bulk_create(...)`; Erfolgsmeldung
      "n Lernkarten erstellt." im Abschnitt; Fehler ebenfalls im Abschnitt;
      Redirect `#lernkarten`.

      `FlashcardToggleView` (POST): `get_object_or_404(Flashcard.objects
      .filter(goal__user=request.user).select_related("goal"), pk=pk)`,
      `is_mastered = not is_mastered`, `save(update_fields=["is_mastered"])`.

      `FlashcardDeleteView` (POST): gleiches Queryset, `delete()`.

      *Detailseite:* `cards = list(self.object.flashcards.all())` (eine
      Abfrage) → `flashcards`, `flashcards_gelernt`, `flashcards_gesamt`.

      *Abschnitts-Meldungen vereinheitlichen:* `ABSCHNITT_TAG = "abschnitt"`;
      `KI_VERLAUF_TAG = "abschnitt ki-verlauf"`, `LERNKARTEN_TAG =
      "abschnitt lernkarten"`. `base.html` überspringt alles mit
      `"abschnitt" in message.extra_tags.split`; das Partial
      `_abschnitt_meldungen.html` zeigt die Meldungen eines Bereichs mit
      passender Alert-Farbe (`error` → `danger`).

- [ ] **Schritt 4: URLs** -- `goals/<pk>/ai/flashcards/` → `goal_ai_flashcards`;
      `flashcards/<pk>/toggle/` → `flashcard_toggle`;
      `flashcards/<pk>/delete/` → `flashcard_delete`.

- [ ] **Schritt 5: UI / Templates**
      - KI-Card: dritter Button "Lernkarten generieren" mit
        `data-ki-aktion`/`data-ladetext="Erstelle Lernkarten..."` → das
        bestehende Script erfasst ihn ohne Änderung.
      - Abschnitt `#lernkarten` vor dem KI-Verlauf: Kopf mit Zähler, darunter
        Fortschritt "x von y gelernt" (`progress` mit ARIA-Werten), dann das
        Akkordeon.
      - `_flashcards.html`: `accordion` mit je einem Item; Kopf =
        `accordion-button collapsed` mit Frage (+ Badge "Gelernt");
        Body = Antwort (`linebreaksbr`) und zwei POST-Formulare
        (Umschalten, Löschen) mit sprechenden `aria-label`s.
        IDs pro Karte (`karte-<pk>`), damit `aria-controls` eindeutig ist.
      - Leerzustand: "Noch keine Lernkarten. …".

- [ ] **Schritt 6: Tests** -- siehe Abschnitt 4.

- [ ] **Schritt 7: Validierung** -- Migration, ruff, Testsuite, Hook;
      Sichtprüfung im Browser über eine zweite Server-Instanz mit
      `AI_MOCK_MODE=True` (keine API-Kosten), Prüfnutzer danach löschen.

## 4. Validierung & Test-Strategie

### Neue Tests (`core/tests/test_flashcards.py`)

| Klasse | Testfälle |
|---|---|
| `ModellTests` | Sortierung (offen vor gelernt, neueste zuerst); CASCADE beim Goal-Löschen |
| `MockTests` | 3 Karten, deterministisch, mit Goal-Titel, kein `_call_openai`-Aufruf |
| `SdkAufrufTests` (Mock aus, SDK gepatcht) | `response_format` mit `json_schema`, `strict: true`, `additionalProperties: false`; konfiguriertes Modell; Prompt enthält nur eigene Goal-Daten und vorhandene Fragen |
| `ParserTests` | gültige Antwort; ungültiges JSON; Liste statt Objekt; `cards` fehlt / kein Array; Einträge mit leerem/fehlendem Text verworfen; < 3 → Fehler; > 5 → gekürzt; Duplikate in Antwort und gegen Bestand; jeder Fehlerfall wird geloggt |
| `RefusalTests` | `message.refusal` → `AIServiceError` mit eigener Meldung (nicht "nicht verfügbar") |
| `GenerierenViewTests` | Karten gespeichert und angehängt (Bestand + Lernstatus bleiben); Redirect `#lernkarten`; Meldung im Abschnitt, genau einmal; Fehler → nichts gespeichert, Meldung im Abschnitt; GET → 405 |
| `VerwaltenViewTests` | Umschalten hin und zurück; Löschen nur dieser Karte; GET → 405 |
| `AnzeigeTests` | Akkordeon mit Frage im Kopf, Antwort im eingeklappten Body; Badge "Gelernt"; Fortschritt; Leerzustand; Query-Anzahl bei 2 und 8 Karten gleich; keine Karten anderer Goals |
| `ScopingTests` | Login-Pflicht für alle drei Routen; fremdes Goal → 404 und Service nicht aufgerufen; fremde Karte umschalten/löschen → 404 ohne Änderung; Gegenprobe mit eigener Karte |

### Anpassung bestehender Tests

| Test | Änderung | Grund |
|---|---|---|
| `LadezustandTests.test_beide_formulare_markiert_mit_ladetext` (`test_ai_views.py`) | erwartet 3 statt 2 markierte KI-Formulare und den dritten Ladetext | Die KI-Card bekommt einen dritten Button; der Test sichert genau diesen Markup-Vertrag. |
| `test_ai_feedback.py`, Test-Schlüssel | Literal ersetzt | Konvention, siehe Abschnitt 1 |

**Kommandos** (im aktiven `.venv`):

```powershell
python manage.py makemigrations core
python manage.py migrate
python manage.py makemigrations --check --dry-run
ruff check .
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

**Abnahmekriterium:** `validate_code.ps1` endet mit Exit-Code 0; alle Bestandstests
bis auf die oben dokumentierte Anpassung unverändert grün; alle neuen Tests grün.
