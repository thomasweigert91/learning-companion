# Code Review: Goals and Sessions — CRUD, Status-Filter und Scoping

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, **63 Tests** (17 aus Feature 1 + 46 neue), `validate_code.ps1` grün.

---

## 1. Abdeckung der Akzeptanzkriterien

### Datenmodell Goal

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `Goal` mit `user`/`title`/`description`/`status`/`created_at`/`updated_at` | `core/models.py:58-82` | ja |
| 2 | Nur `planned`/`in-progress`/`done`, Default `planned`, `full_clean()` lehnt ab | `test_goal_default_status_is_planned`, `test_invalid_status_rejected_by_full_clean`, `test_all_three_statuses_are_valid` | ja |
| 3 | `__str__` liefert Titel | `test_goal_str_returns_title` | ja |

### Datenmodell LearningSession

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 4 | `LearningSession` mit `goal`/`date`/`duration`/`notes`/`tags` | `core/models.py:88-112` | ja |
| 5 | `duration` nur > 0 | `test_duration_zero_rejected`, `test_duration_negative_rejected`, `test_duration_positive_accepted` | ja |
| 6 | Löschen des Goals kaskadiert | `test_deleting_goal_cascades_to_sessions` | ja |
| 7 | `__str__` menschenlesbar | `test_session_str_is_human_readable` (`"Django lernen am 15.09.2026"`) | ja |

### CRUD-Views Goal

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 8 | Fünf Views erreichbar | `core/urls.py:28-32`; alle fünf in den CRUD- und Scoping-Tests aufgerufen | ja |
| 9 | Liste zeigt nur eigene Goals (Kontext **und** HTML) | `test_goal_list_shows_only_own_goals` | ja |
| 10 | `user` serverseitig gesetzt, nicht per POST überschreibbar | `test_goal_create_assigns_current_user`, `test_goal_create_ignores_user_field_in_post` | ja |
| 11 | Edit und Delete wirken in der DB | `test_goal_update_persists`, `test_goal_delete_removes_goal` | ja |

### CRUD-Views LearningSession

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 12 | Fünf Views erreichbar | `core/urls.py:34-38` | ja |
| 13 | Liste nur eigene Sessions (über `goal__user`) | `test_session_list_shows_only_own_sessions` | ja |
| 14 | Nur eigene Goals wählbar; fremde Goal-ID → 200 + Formularfehler, keine Session | `test_session_form_only_offers_own_goals`, `test_session_create_with_foreign_goal_rejected` | ja |

### Status-Filter

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 15 | `?status=` filtert je Status | `test_filter_by_status_planned` / `_in_progress` / `_done` | ja |
| 16 | Ohne Parameter alle eigenen Goals | `test_no_filter_returns_all_own_goals` | ja |
| 17 | Ungültiger Wert → 200, ungefiltert | `test_invalid_status_value_returns_all`, `test_empty_status_value_returns_all` | ja |
| 18 | Filter leakt keine fremden Goals | `test_filter_does_not_leak_foreign_goals` | ja |

### Scoping und Zugriffskontrolle

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 19 | Alle zehn Views → 302 auf Login | `test_all_goal_views_require_login`, `test_all_session_views_require_login` (Schleife über je 5 URLs, mit `assertEqual(len(urls), 5)` gegen stilles Schrumpfen abgesichert) | ja |
| 20 | Fremdes Goal: Detail/Edit/Delete → 404, keine Daten in der Response | `test_foreign_goal_detail_returns_404`, `test_foreign_goal_edit_get_returns_404` | ja |
| 21 | POST auf fremdes Goal-Edit ändert nichts | `test_foreign_goal_edit_post_does_not_change_data` | ja |
| 22 | POST auf fremdes Goal-Delete löscht nicht | `test_foreign_goal_delete_post_does_not_delete` | ja |
| 23 | Dieselben vier Fälle für `LearningSession`, separat getestet | `FremdzugriffSessionTests` (4 Tests + Listen-Gegenprobe) | ja |

### Tests und Regression

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 24 | Tests decken Modell, CRUD, Filter, Scoping ab | `test_goals.py`, `test_sessions.py`, `test_scoping.py` | ja |
| 25 | Die 17 Tests aus Feature 1 laufen unverändert weiter | 63 Tests gesamt, kein Testmodul aus Feature 1 angefasst | ja |
| 26 | `check` und `test` Exit-Code 0 | Hook `validate_code.ps1` | ja |
| 27 | Neue Migration eingecheckt, `--check --dry-run` sauber | `core/migrations/0002_goal_learningsession.py`; "No changes detected" | ja |

**28 von 28 Kriterien erfüllt.** (Kriterium 19 deckt die zehn Views in zwei Testmethoden ab.)

## 2. Sicherheit

**Auth-Bypass — geprüft, kein Befund.**

Das Scoping folgt durchgängig dem Muster aus Feature 1: `OwnGoalMixin.get_queryset()` filtert auf `user=request.user`, `OwnSessionMixin.get_queryset()` auf `goal__user=request.user`. Weil **gefiltert statt nachträglich geprüft** wird, ist ein fremder PK im Queryset gar nicht enthalten — `get_object()` liefert für Detail, Edit und Delete automatisch 404. Eine vergessene Einzelprüfung kann es in dieser Konstruktion nicht geben.

Drei Stellen, die über eine reine Statuscode-Prüfung hinaus abgesichert sind:

1. **Massenzuweisung auf `user`.** `GoalForm.fields` enthält `user` nicht; die Zuordnung setzt `GoalCreateView.form_valid()` aus `request.user`. `test_goal_create_ignores_user_field_in_post` schickt gezielt ein zusätzliches `user=<pk_von_B>` mit und belegt, dass das Goal trotzdem auf A landet.
2. **Fremdes Goal an einer eigenen Session.** `LearningSessionForm.__init__` schränkt das `goal`-Queryset auf die Goals des Nutzers ein. Das ist nicht bloß kosmetisch im Dropdown: Ein POST mit fremder Goal-ID läuft serverseitig als ungültige Auswahl auf (`test_session_create_with_foreign_goal_rejected` prüft Status 200, `form.errors["goal"]` und die unveränderte Objektzahl).
3. **Schreibpfade.** Für Goal **und** Session wird nach dem abgewiesenen Edit- bzw. Delete-POST per `refresh_from_db()` respektive `.exists()` nachgewiesen, dass die Daten von B unverändert sind. Ein 404 allein würde nicht belegen, dass vorher nichts geschrieben wurde.

**SQL-Injection — keine Angriffsfläche.** Ausschließlich ORM-Zugriffe, kein `raw()`, kein `extra()`, keine String-Interpolation in Queries. Der Query-Parameter `status` wird nicht in eine Query interpoliert, sondern gegen `Goal.Status.values` geprüft und nur bei Treffer als `filter()`-Argument verwendet.

**CSRF und Methodensicherheit.** Alle schreibenden Formulare tragen `{% csrf_token %}`. Gelöscht wird ausschließlich per POST — `test_goal_delete_requires_post` belegt, dass ein GET auf die Delete-URL die Bestätigungsseite zeigt und den Datensatz stehen lässt.

**Kein Information Leak über Statuscodes.** Fremde Objekte liefern 404, nicht 403. Damit ist aus der Antwort nicht ableitbar, ob ein Objekt mit dieser ID überhaupt existiert.

## 3. Hinweise ohne Blocker-Charakter

1. **`LearningSession` hat keinen `MaxValueValidator` auf `duration`.** Eine Sitzung von 10.000 Minuten ist technisch eintragbar. Nicht gefordert, fachlich aber irgendwann sinnvoll zu begrenzen.
2. **`date` liegt frei in der Zukunft.** Lernsitzungen lassen sich auf beliebige künftige Daten eintragen. Das kann gewollt sein (Planung) — falls nicht, wäre eine `clean()`-Prüfung der Ort dafür.
3. **Keine Pagination auf beiden Listen.** Bei vielen Goals oder Sessions wächst die Seite unbegrenzt. Im Ticket explizit Out-of-Scope.
4. **`select_related` nur bei Sessions.** `OwnSessionMixin` nutzt `select_related("goal")`; die Goal-Liste braucht keinen Join. In `goal_detail.html` erzeugt `goal.sessions.all` eine zusätzliche Query — bei einem Detail-Objekt unkritisch.
5. **Aus Feature 1 unverändert offen:** Dev-Fallback für `SECRET_KEY`, `DEBUG` per Default `True`, kein Brute-Force-Schutz am Login. Vor einem Deployment zu härten.

## 4. Formatierung und tote Code-Pfade

Imports sortiert und vollständig genutzt, keine auskommentierten Reste, keine ungenutzten Views, URL-Namen konsistent (`goal_*` / `session_*`). Alle acht neuen Templates werden von je einer View referenziert; alle zehn URL-Namen werden aus Templates oder Tests heraus aufgelöst. `manage.py check` meldet 0 Issues.

Zwei Stellen, die bewusst so aussehen und kein toter Code sind:

- `GoalCreateView` und `SessionCreateView` erben **nicht** von den Own-Mixins, sondern nur von `LoginRequiredMixin`. Das ist korrekt: Beim Anlegen wird kein bestehendes Objekt geladen, es gibt also nichts zu scopen. Die Zuordnung entsteht in `form_valid()` bzw. über die eingeschränkte Goal-Auswahl.
- `SessionFormUserMixin` ist von den Own-Mixins getrennt, weil `SessionCreateView` den Form-Kwarg braucht, aber kein Objekt-Scoping — eine Zusammenlegung hätte für Create ein unnötiges Queryset erzwungen.

## 5. Abweichungen vom Plan

| Abweichung | Begründung |
|---|---|
| 46 statt der ~40 geplanten neuen Tests | Vier Ergänzungen: `test_all_three_statuses_are_valid`, `test_empty_status_value_returns_all` (`?status=` leer ist der realistische Fall beim Absenden des Filter-Formulars mit "Alle"), `test_session_create_with_invalid_duration_rejected` und `test_own_goal_edit_and_delete_work` als zweite Gegenprobe. |
| `GegenprobeTests` als eigene Klasse statt eines Einzeltests | Der Plan sah `test_own_goal_and_session_remain_accessible` vor; daraus wurden zwei Tests (lesend und schreibend), damit die 404-Tests nicht durch eine global kaputte View trivial erfüllbar sind. |

Keine Abweichung bei Dateien, Modellfeldern, Routen oder Namensgebung — die Umsetzung entspricht Abschnitt 1 und 2 des Plans vollständig.

## 6. Fazit

Alle 28 Akzeptanzkriterien sind erfüllt und durch benannte Tests oder Kommando-Exit-Codes belegt. Die Mandantentrennung ist für beide Entitäten strukturell über das Queryset gelöst und sowohl für lesende als auch für schreibende Zugriffe nachgewiesen; die zwei klassischen Lücken dieser Feature-Art — Massenzuweisung auf `user` und eine fremde Fremdschlüssel-ID im Formular — sind gezielt geschlossen und getestet. Keine Sicherheitsbefunde, keine toten Pfade, keine Regression in Feature 1.

**Status: APPROVED**
