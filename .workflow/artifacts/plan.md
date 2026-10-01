# Implementierungs-Plan: Persistente KI-Historie zu Lernzielen

## 1. Betroffene Dateien

**Vorab-Aufgabe (.env)** -- bereits umgesetzt und verifiziert:

- Ändern: `requirements.txt` (`python-dotenv>=1.0,<2.0`)
- Ändern: `learning_companion/settings.py` (`load_dotenv(BASE_DIR / ".env")`, `TEST_RUNNER`)
- Neu: `core/test_runner.py` (`OfflineTestRunner`)
- Neu: `core/tests/test_offline.py`

**Feature 8**

- Ändern: `core/models.py` (Modell `AIFeedback`)
- Neu: `core/migrations/0004_aifeedback.py` (per `makemigrations` erzeugt)
- Ändern: `core/admin.py` (Registrierung `AIFeedback`)
- Ändern: `core/views.py` (Session-Speicher → DB; Kontext der Detailseite; zwei Lösch-Views)
- Ändern: `core/urls.py` (zwei neue Routen)
- Ändern: `core/templates/core/goal_detail.html` (KI-Card aus DB, Abschnitt "KI-Verlauf")
- Neu: `core/templates/core/_ai_timeline.html` (Timeline-Partial)
- Neu: `core/templates/core/aifeedback_confirm_clear.html` (Bestätigung "Alle zurücksetzen")
- Ändern: `core/templates/core/goal_confirm_delete.html` (Hinweis auf mitgelöschte KI-Historie)
- Ändern: `core/templates/base.html` (wenige Zeilen CSS für die Timeline)
- Ändern: `core/tests/test_ai_views.py` (Session-Asserts → DB-Asserts, siehe Abschnitt 4)
- Neu: `core/tests/test_ai_feedback.py`

**Bewusst unverändert:** `core/services/ai_service.py`. Der Service liefert weiterhin
nur Text bzw. eine Liste und schreibt nichts in die DB -- dieser Vertrag ist durch
`test_service_does_not_touch_database` festgeschrieben und hält den Service frei
von Persistenz-Details. Die "Service-Anpassung" findet an der Aufrufstelle statt:
die View nimmt das Ergebnis entgegen und persistiert es.

## 2. Datenmodelle & Migrationen

```python
class AIFeedback(models.Model):
    """Ein gespeichertes KI-Ergebnis zu genau einem Goal.

    Besitzer wie bei LearningSession/Resource nur über goal__user.
    """

    class FeedbackType(models.TextChoices):
        SUMMARY = "summary", "Zusammenfassung"
        NEXT_STEPS = "next_steps", "Naechste Schritte"

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="ai_feedbacks")
    feedback_type = models.CharField(max_length=20, choices=FeedbackType.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def steps(self):
        return [zeile for zeile in self.content.splitlines() if zeile.strip()]
```

- **Speicherformat der Schritte:** eine Zeile pro Schritt. Der Service zerlegt die
  Modellantwort bereits zeilenweise; ein einzelner Schritt enthält daher nie einen
  Zeilenumbruch, das Format ist verlustfrei umkehrbar.
- **Badge-Labels** bewusst "Zusammenfassung" / "Naechste Schritte" -- *nicht*
  "Fortschrittszusammenfassung" / "Naechste Lernschritte". Diese beiden Wörter
  sind die Überschriften des Ergebnisbereichs, deren Abwesenheit vor der ersten
  Nutzung `test_no_result_block_before_first_use` prüft.
- **`-pk` als Tiebreaker:** zwei Einträge in derselben Mikrosekunde (Tests,
  Doppelklick) hätten sonst keine definierte Reihenfolge.
- **Migration:** `python manage.py makemigrations core` → `0004_aifeedback`;
  danach `migrate` auf die Dev-Datenbank. Rein additiv, keine bestehende Tabelle
  wird verändert, kein Datenmigrationsschritt nötig.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Setup & Models** -- `AIFeedback` in `core/models.py`,
      Migration erzeugen und anwenden, Admin-Registrierung
      (`list_display = ("goal", "feedback_type", "created_at")`,
      `list_filter = ("feedback_type",)`, `search_fields = ("goal__title", "content")`).

- [ ] **Schritt 2: Business-Logik / Views**

      *Speichern* -- `GoalAIActionMixin` verliert `session_key` und
      `build_result`, bekommt stattdessen `feedback_type` und `to_content()`:
      ```python
      try:
          ergebnis = self.run_service(goal)
      except ai_service.AIServiceError as fehler:
          messages.error(request, str(fehler))
      else:
          AIFeedback.objects.create(
              goal=goal, feedback_type=self.feedback_type,
              content=self.to_content(ergebnis),
          )
      ```
      `GoalSummaryView.to_content` gibt den Text zurück,
      `GoalNextStepsView.to_content` verbindet die Liste mit `"\n"`. Die
      Konstanten `AI_SUMMARY_KEY` / `AI_NEXT_STEPS_KEY` entfallen ersatzlos.

      *Anzeige* -- `GoalDetailView.get_context_data`:
      ```python
      feedbacks = list(self.object.ai_feedbacks.all())   # genau 1 Abfrage
      context["ai_feedbacks"] = feedbacks
      context["ai_summary"] = next((f for f in feedbacks if f.feedback_type == SUMMARY), None)
      context["ai_next_steps"] = next((f for f in feedbacks if f.feedback_type == NEXT_STEPS), None)
      ```
      Die "neuesten je Typ" werden aus der bereits geladenen Liste gewählt statt
      mit zwei weiteren Abfragen. `ai_summary`/`ai_next_steps` werden nur gesetzt,
      wenn ein Eintrag existiert (der bestehende Test prüft die Abwesenheit des
      Schlüssels im Kontext).

      *Löschen* --
      - `AIFeedbackDeleteView(LoginRequiredMixin, View)`, nur `post()`:
        `get_object_or_404(AIFeedback.objects.filter(goal__user=request.user)
        .select_related("goal"), pk=pk)` → `delete()` → Erfolgsmeldung → Redirect
        auf `goal.get_absolute_url() + "#ki-verlauf"`. GET → 405 durch `View`.
      - `AIFeedbackClearView(LoginRequiredMixin, View)`: Goal per
        `get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)`;
        `get()` rendert die Bestätigung mit Anzahl, `post()` löscht
        `goal.ai_feedbacks.all()` und meldet die Anzahl.

      Beide folgen dem Muster des Projekts: gefiltert statt nachträglich geprüft
      -- ein fremder PK ist im Queryset nicht enthalten, daraus folgt 404, bevor
      irgendetwas gelöscht wird.

- [ ] **Schritt 3: URLs** --
      `goals/<int:pk>/ai/history/clear/` → `goal_ai_history_clear`;
      `ai-feedback/<int:pk>/delete/` → `ai_feedback_delete`.
      Der Präfix `goal…` markiert in der Navbar automatisch "Goals"; für
      `ai_feedback_delete` ist das ohne Belang, die Route rendert nie eine Seite.

- [ ] **Schritt 4: UI / Templates**
      - `goal_detail.html`, KI-Card: die Blöcke "Fortschrittszusammenfassung" und
        "Naechste Lernschritte" lesen aus `ai_summary.content` bzw.
        `ai_next_steps.steps` und zeigen zusätzlich das Erzeugungsdatum.
      - Neuer Abschnitt in der Hauptspalte: Card "KI-Verlauf" (`id="ki-verlauf"`,
        `aria-labelledby`) mit Eintragsanzahl im Kopf und Button
        "Alle zuruecksetzen" (nur bei vorhandenen Einträgen, `btn-outline-danger`).
      - `_ai_timeline.html`: `<ol class="lc-timeline">` -- semantisch eine
        geordnete Liste, neueste zuerst. Je Eintrag: Typ-Badge
        (Summary `text-bg-info`, Schritte `text-bg-warning`, jeweils mit Icon und
        Text), `<time datetime="{{ f.created_at|date:'c' }}">`, Inhalt
        (`linebreaksbr` bzw. `<ol>` aus `steps`), Löschen-Button als POST-Form mit
        `aria-label="KI-Eintrag (<Typ>) vom <Datum> loeschen"`.
      - Leerzustand: "Noch keine KI-Ergebnisse gespeichert."
      - `aifeedback_confirm_clear.html`: Card im Stil der übrigen
        Lösch-Bestätigungen, nennt Goal und Anzahl, POST + Abbrechen.
      - `goal_confirm_delete.html`: Hinweis ergänzt um Ressourcen und KI-Verlauf.
      - `base.html`: CSS für die Timeline-Linie und -Punkte (`.lc-timeline`).

- [ ] **Schritt 5: Tests** -- siehe Abschnitt 4.

- [ ] **Schritt 6: Validierung** -- `makemigrations --check --dry-run`, `ruff check .`,
      `python manage.py test`, `validate_code.ps1`; Sichtprüfung im Browser mit
      temporärem Prüfnutzer (Mock-Modus erzwungen, damit die Sichtprüfung keine
      API-Kosten verursacht), anschließend Prüfnutzer wieder löschen.

## 4. Validierung & Test-Strategie

### Anpassung bestehender Tests (`core/tests/test_ai_views.py`)

Vier Tests prüfen den Session-Speicher, den dieses Ticket ersetzt, ein fünfter
den Listen-Typ im Kontext. Sie werden auf den Datenbank-Vertrag **umgestellt**,
ihre Absicht bleibt erhalten:

| Test | bisher | künftig |
|---|---|---|
| `test_actions_not_triggered_by_get` | kein Session-Schlüssel nach GET | `AIFeedback.objects.count() == 0` nach GET |
| `test_results_are_not_persisted_in_database` | Ergebnis in Session, nicht in DB | **ersetzt** durch `test_results_are_persisted_per_type`: je ein Eintrag pro Typ, Goal-Felder unverändert |
| `test_failed_action_leaves_no_result_in_session` | kein Session-Schlüssel nach Fehler | umbenannt zu `…_leaves_no_result`: kein `AIFeedback` nach Fehler |
| `test_own_goal_actions_work` | Session-Schlüssel vorhanden | je ein `AIFeedback` pro Typ für das eigene Goal |
| `test_next_steps_action_redirects_and_shows_list` | `context["ai_next_steps"]` ist Liste | `context["ai_next_steps"].steps` ist Liste (2–3 Einträge) |

Zusätzlich entfällt der Import der Session-Konstanten. Alle anderen Tests der
Datei bleiben unverändert.

### Neue Tests (`core/tests/test_ai_feedback.py`)

| Testklasse | Testfall | Prüft |
|---|---|---|
| `ModellTests` | `test_sortierung_neueste_zuerst` | `-created_at`, bei Gleichstand `-pk` |
| | `test_steps_aus_zeilen` | Leerzeilen werden ignoriert |
| | `test_cascade_beim_goal_loeschen` | Goal löschen → Einträge weg |
| `SpeichernTests` | `test_summary_wird_gespeichert` | Typ `summary`, Inhalt = Service-Ergebnis |
| | `test_next_steps_zeilenweise_gespeichert` | Typ `next_steps`, `steps` = Service-Liste |
| | `test_jede_aktion_ein_neuer_eintrag` | zwei Aufrufe → zwei Einträge (Historie statt Überschreiben) |
| | `test_fehler_speichert_nichts` | `AIServiceError` → 0 Einträge |
| | `test_echter_pfad_speichert_modellantwort` | Mock aus, SDK gepatcht → gespeicherter Inhalt = gepatchte Antwort |
| `AnzeigeTests` | `test_timeline_zeigt_alle_eintraege` | Badge, `<time datetime>`, Inhalte, neueste zuerst |
| | `test_leerzustand` | Hinweistext, kein "Alle zuruecksetzen" |
| | `test_neuestes_ergebnis_in_ki_card` | KI-Card zeigt den jüngsten Eintrag je Typ |
| | `test_abfragen_unabhaengig_von_eintragszahl` | Query-Anzahl bei 2 und 8 Einträgen gleich |
| | `test_eintraege_anderer_goals_unsichtbar` | Goal A2 zeigt keine Einträge von A |
| `LoeschenTests` | `test_einzelnen_eintrag_loeschen` | nur dieser Eintrag weg, Redirect auf `#ki-verlauf` |
| | `test_einzel_loeschen_nicht_per_get` | 405, nichts gelöscht |
| | `test_alle_zuruecksetzen_bestaetigung` | GET zeigt Bestätigung mit Anzahl, löscht nichts |
| | `test_alle_zuruecksetzen_betrifft_nur_dieses_goal` | Einträge von Goal A2 bleiben |
| `ScopingTests` | `test_login_pflicht` | beide Routen → Login-Redirect |
| | `test_fremder_eintrag_404_ohne_loeschung` | Eintrag von B bleibt erhalten |
| | `test_fremdes_goal_zuruecksetzen_404` | GET und POST → 404, Einträge von B bleiben |

Die Testklassen erzwingen den Mock zusätzlich lokal per `@override_settings`; der
`OfflineTestRunner` sichert global ab.

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
außer den fünf oben dokumentierten Anpassungen unverändert grün; alle neuen Tests
grün.
