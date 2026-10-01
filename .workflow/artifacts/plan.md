# Implementierungs-Plan: Goals and Sessions — CRUD, Status-Filter und Scoping

## 1. Betroffene Dateien

**Ändern**

- Ändern: `core/models.py` — Modelle `Goal` und `LearningSession` ergänzen
- Ändern: `core/forms.py` — `GoalForm` und `LearningSessionForm` ergänzen
- Ändern: `core/views.py` — Scoping-Mixins und zehn CRUD-Views ergänzen
- Ändern: `core/urls.py` — zehn Routen ergänzen
- Ändern: `core/admin.py` — `Goal` und `LearningSession` registrieren
- Ändern: `core/templates/base.html` — Navigationseinträge "Goals" und "Sessions"
- Ändern: `core/templates/core/home.html` — Einstiegslinks für eingeloggte Nutzer

**Neu — Migration**

- Neu: `core/migrations/0002_goal_learningsession.py` (per `makemigrations` erzeugt, eingecheckt)

**Neu — Templates Goal**

- Neu: `core/templates/core/goal_list.html`
- Neu: `core/templates/core/goal_detail.html`
- Neu: `core/templates/core/goal_form.html`
- Neu: `core/templates/core/goal_confirm_delete.html`

**Neu — Templates LearningSession**

- Neu: `core/templates/core/learningsession_list.html`
- Neu: `core/templates/core/learningsession_detail.html`
- Neu: `core/templates/core/learningsession_form.html`
- Neu: `core/templates/core/learningsession_confirm_delete.html`

**Neu — Tests**

- Neu: `core/tests/test_goals.py` — Modell, CRUD und Status-Filter für `Goal`
- Neu: `core/tests/test_sessions.py` — Modell, CRUD und Goal-Bindung für `LearningSession`
- Neu: `core/tests/test_scoping.py` — Mandantentrennung A gegen B für beide Entitäten

**Unverändert:** `learning_companion/settings.py` (keine neue App, keine neue Abhängigkeit), `requirements.txt`, `core/signals.py`, `core/apps.py`, alle Dateien unterhalb `.workflow/` sowie die drei bestehenden Testmodule aus Feature 1.

## 2. Datenmodelle & Migrationen

### `Goal` (`core/models.py`)

Status über `models.TextChoices`, damit Choices, Labels und Validierung aus einer Quelle stammen:

```python
class Status(models.TextChoices):
    PLANNED = "planned", "Geplant"
    IN_PROGRESS = "in-progress", "In Arbeit"
    DONE = "done", "Erledigt"
```

| Feld | Typ | Optionen |
| --- | --- | --- |
| `user` | `ForeignKey` | `settings.AUTH_USER_MODEL`, `on_delete=models.CASCADE`, `related_name="goals"` |
| `title` | `CharField` | `max_length=200` (Pflichtfeld) |
| `description` | `TextField` | `blank=True` |
| `status` | `CharField` | `max_length=20`, `choices=Status.choices`, `default=Status.PLANNED` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

- `Meta.ordering = ["-updated_at"]`
- `__str__` → `self.title`
- `get_absolute_url()` → `reverse("core:goal_detail", args=[self.pk])`

Die Längenbegrenzung `max_length=20` deckt den längsten Wert `"in-progress"` (11 Zeichen) ab. Die Ablehnung abweichender Werte durch `full_clean()` leistet der `choices`-Validator.

### `LearningSession` (`core/models.py`)

| Feld | Typ | Optionen |
| --- | --- | --- |
| `goal` | `ForeignKey` | `Goal`, `on_delete=models.CASCADE`, `related_name="sessions"` |
| `date` | `DateField` | — |
| `duration` | `PositiveIntegerField` | `validators=[MinValueValidator(1)]`, `help_text="Dauer in Minuten"` |
| `notes` | `TextField` | `blank=True` |
| `tags` | `ManyToManyField` | `Tag`, `blank=True`, `related_name="sessions"` |

- `Meta.ordering = ["-date", "-pk"]`
- `__str__` → `f"{self.goal.title} am {self.date:%d.%m.%Y}"`
- `get_absolute_url()` → `reverse("core:session_detail", args=[self.pk])`

Zu `duration`: `PositiveIntegerField` allein lässt die 0 zu, deshalb zusätzlich `MinValueValidator(1)`. Negative Werte fängt bereits der Feldtyp ab. Beides greift in `full_clean()` und damit auch im `ModelForm`.

Die Kaskade beim Löschen eines Goals kommt aus `on_delete=models.CASCADE` — kein eigener Code nötig, aber per Test belegt.

Der Besitz einer Session wird **nicht** redundant gespeichert, sondern immer über `goal__user` aufgelöst. Damit kann ein Goal und seine Sessions nicht auseinanderlaufen.

### Migration

- `python manage.py makemigrations core` erzeugt `0002_goal_learningsession.py` (zwei `CreateModel`-Operationen plus die M2M-Zwischentabelle zu `Tag`).
- Danach `python manage.py migrate`.
- Keine Datenmigration: beide Tabellen sind neu, bestehende Daten aus Feature 1 bleiben unberührt.
- Abschließend `makemigrations --check --dry-run` als Nachweis, dass Modelle und Migrationen deckungsgleich sind.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Modelle und Migration** — `Goal` (inkl. innerer `Status`-TextChoices-Klasse) und `LearningSession` in `core/models.py` ergänzen, jeweils mit `__str__`, `get_absolute_url` und `Meta.ordering`; `MinValueValidator` importieren; `core/admin.py` um `GoalAdmin` (`list_display`, `list_filter` auf `status`) und `LearningSessionAdmin` (`list_display`, `filter_horizontal` auf `tags`) erweitern. Dann `makemigrations core` und `migrate`. Abnahme: `manage.py check` Exit-Code 0, `0002_*.py` existiert.

- [ ] **Schritt 2: Scoping-Mixins** — In `core/views.py` zwei Mixins ergänzen, die das aus dem Profil-Feature bekannte Muster fortführen:
  - `OwnGoalMixin(LoginRequiredMixin)` mit `model = Goal` und `get_queryset()` → `Goal.objects.filter(user=self.request.user)`.
  - `OwnSessionMixin(LoginRequiredMixin)` mit `model = LearningSession` und `get_queryset()` → `LearningSession.objects.filter(goal__user=self.request.user).select_related("goal")`.
  
  Beide filtern grundsätzlich, nicht erst nach einer Berechtigungsprüfung. Ein fremder PK ist damit im Queryset schlicht nicht enthalten und führt in `get_object()` automatisch zu 404 — für Detail, Edit und Delete gleichermaßen, ohne dass eine Prüfung vergessen werden kann.

- [ ] **Schritt 3: Goal-CRUD und Status-Filter** — `GoalForm(ModelForm)` in `core/forms.py` mit `fields = ["title", "description", "status"]` — `user` ist bewusst **nicht** enthalten und damit nicht per POST setzbar. In `core/views.py`: `GoalListView`, `GoalDetailView`, `GoalCreateView`, `GoalUpdateView`, `GoalDeleteView`. `GoalCreateView` setzt in `form_valid()` `form.instance.user = self.request.user` und erbt nur `LoginRequiredMixin` (kein Queryset-Scoping nötig, da kein Objekt geladen wird). `GoalDeleteView.success_url = reverse_lazy("core:goal_list")`.
  
  Der Status-Filter sitzt in `GoalListView.get_queryset()`: Basis ist das gescopte Queryset des Mixins, darauf wird `status = self.request.GET.get("status")` angewandt — aber nur, wenn der Wert in `Goal.Status.values` enthalten ist. Ein unbekannter Wert wird stillschweigend ignoriert und liefert die ungefilterte eigene Liste (Status 200 statt Fehler). Der aktive Filter und die Status-Auswahl kommen über `get_context_data()` ins Template.

- [ ] **Schritt 4: LearningSession-CRUD mit Goal-Bindung** — `LearningSessionForm(ModelForm)` mit `fields = ["goal", "date", "duration", "notes", "tags"]`, `DateInput(type="date")` als Widget für `date` und `CheckboxSelectMultiple` für `tags`. Entscheidend: Der Form nimmt im `__init__` einen `user` entgegen und setzt `self.fields["goal"].queryset = Goal.objects.filter(user=user)`. Damit stehen nur eigene Goals zur Auswahl **und** ein POST mit fremder Goal-ID wird serverseitig als ungültige Auswahl abgewiesen (Status 200 mit Formularfehler, keine Session) — die Einschränkung ist also nicht bloß kosmetisch im Dropdown.
  
  Die fünf Views (`SessionListView`, `SessionDetailView`, `SessionCreateView`, `SessionUpdateView`, `SessionDeleteView`) reichen den User über `get_form_kwargs()` an den Form durch. `SessionCreateView` erbt nur `LoginRequiredMixin`; die Zuordnung entsteht implizit über das gewählte Goal.

- [ ] **Schritt 5: URLs** — `core/urls.py` um zehn Routen erweitern: `/goals/`, `/goals/new/`, `/goals/<int:pk>/`, `/goals/<int:pk>/edit/`, `/goals/<int:pk>/delete/` sowie analog unter `/sessions/`. Die statischen Segmente (`new`) stehen vor den `<int:pk>`-Routen; eine Kollision ist durch den `int`-Converter ohnehin ausgeschlossen. Namen: `goal_list`, `goal_create`, `goal_detail`, `goal_edit`, `goal_delete` und `session_*` analog.

- [ ] **Schritt 6: Templates** — Die acht neuen Templates erweitern `base.html`. `goal_list.html` enthält das Filter-Formular (GET, `<select name="status">` mit den Choices plus Option "Alle") und markiert den aktiven Filter; `goal_detail.html` listet die zugehörigen Sessions über `goal.sessions.all` und verlinkt Edit/Delete. Die beiden `*_confirm_delete.html` sind POST-Formulare mit `{% csrf_token %}` — kein Löschen per GET. `base.html` und `home.html` bekommen Navigationslinks für eingeloggte Nutzer. Formular-Templates zeigen `{{ form.errors }}` sichtbar an.

- [ ] **Schritt 7: Tests** — Die drei neuen Testmodule gemäß Abschnitt 4 schreiben.

- [ ] **Schritt 8: Gesamtvalidierung** — `manage.py check`, `makemigrations --check --dry-run`, `manage.py test` (bestehende 17 plus neue Tests) und `.\.workflow\hooks\validate_code.ps1` ausführen; alles mit Exit-Code 0.

## 4. Validierung & Test-Strategie

### `core/tests/test_goals.py`

Modell:

- `test_goal_str_returns_title`
- `test_goal_default_status_is_planned` — ein ohne `status` angelegtes Goal hat `planned`.
- `test_invalid_status_rejected_by_full_clean` — `status="unsinn"` → `ValidationError` aus `full_clean()`.

CRUD:

- `test_goal_list_shows_only_own_goals` — A sieht sein Goal, nicht das von B; geprüft über `response.context["object_list"]` **und** `assertNotContains` auf den Titel von B.
- `test_goal_create_assigns_current_user` — POST auf `/goals/new/` → Goal gehört A.
- `test_goal_create_ignores_user_field_in_post` — POST mit zusätzlichem `user=<pk_von_B>` → das Goal gehört trotzdem A (belegt, dass `user` nicht per Form setzbar ist).
- `test_goal_detail_shows_own_goal` — 200 mit Titel.
- `test_goal_update_persists` — POST auf Edit, danach `refresh_from_db()`; Titel und Status aktualisiert.
- `test_goal_delete_removes_goal` — POST auf Delete → Redirect, `Goal.objects.filter(pk=...).exists()` ist `False`.
- `test_goal_delete_requires_post` — GET auf die Delete-URL liefert 200 (Bestätigungsseite) und löscht **nicht**.

Status-Filter:

- `test_filter_by_status_planned` / `test_filter_by_status_in_progress` / `test_filter_by_status_done` — je nur die passenden eigenen Goals.
- `test_no_filter_returns_all_own_goals`
- `test_invalid_status_value_returns_all` — `?status=unsinn` → Status 200 und alle eigenen Goals.
- `test_filter_does_not_leak_foreign_goals` — B hat ein Goal mit `done`; A ruft `?status=done` auf und sieht es nicht.

### `core/tests/test_sessions.py`

Modell:

- `test_session_str_is_human_readable` — enthält Goal-Titel und Datum.
- `test_duration_zero_rejected` und `test_duration_negative_rejected` — `full_clean()` wirft `ValidationError`.
- `test_duration_positive_accepted`
- `test_deleting_goal_cascades_to_sessions` — nach `goal.delete()` gilt `LearningSession.objects.filter(goal_id=alte_id).count() == 0`.

CRUD und Goal-Bindung:

- `test_session_list_shows_only_own_sessions` — gefiltert über `goal__user`.
- `test_session_create_with_own_goal` — Session wird angelegt, Redirect.
- `test_session_form_only_offers_own_goals` — das `goal`-Queryset des Formulars enthält A's Goal, nicht B's.
- `test_session_create_with_foreign_goal_rejected` — POST mit `goal=<pk_von_B>` → Status 200, `"goal"` in `form.errors`, `LearningSession.objects.count()` unverändert.
- `test_session_detail_update_delete` — Detail 200, Update persistiert, Delete entfernt den Datensatz.
- `test_session_tags_are_saved` — ausgewählte `Tag`-IDs landen an der Session.

### `core/tests/test_scoping.py`

Der Kern des Tickets. Zwei Nutzer A und B, jeder mit einem Goal und einer Session.

Anonymer Zugriff:

- `test_all_goal_views_require_login` und `test_all_session_views_require_login` — je eine Schleife über alle fünf URLs, jeweils `assertRedirects` auf `/accounts/login/?next=...`. Damit ist das Kriterium "alle zehn Views" vollständig und nicht nur stichprobenartig abgedeckt.

Fremdzugriff Goal:

- `test_foreign_goal_detail_returns_404`
- `test_foreign_goal_edit_get_returns_404`
- `test_foreign_goal_edit_post_does_not_change_data` — nach dem abgewiesenen POST per `refresh_from_db()` prüfen, dass Titel und Status von B unverändert sind.
- `test_foreign_goal_delete_post_does_not_delete` — Status 404 und `Goal.objects.filter(pk=b.pk).exists()` ist weiterhin `True`.

Fremdzugriff LearningSession (dieselben vier Fälle, separat getestet):

- `test_foreign_session_detail_returns_404`
- `test_foreign_session_edit_get_returns_404`
- `test_foreign_session_edit_post_does_not_change_data`
- `test_foreign_session_delete_post_does_not_delete`

Gegenprobe:

- `test_own_goal_and_session_remain_accessible` — stellt sicher, dass das Scoping nicht einfach alles sperrt und die 404-Tests dadurch trivial erfüllt wären.

### Testdaten

- `setUpTestData` legt je Testklasse zwei Nutzer, deren Goals in unterschiedlichen Status und je eine Session an; Profile entstehen weiterhin automatisch per Signal.
- `Tag`-Instanzen werden für die Session-Tests direkt angelegt. Keine Fixture-Dateien, keine neuen Abhängigkeiten.

### Auszuführende Kommandos

```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

### Definition of Done

Alle vier Kommandos enden mit Exit-Code 0, die 17 Tests aus Feature 1 laufen unverändert mit durch, `core/migrations/0002_goal_learningsession.py` ist eingecheckt, und jedes der 28 Akzeptanzkriterien aus `.workflow/artifacts/ticket.md` ist durch mindestens einen benannten Test oder einen Kommando-Exit-Code belegt.
