# Ticket: Goals and Sessions — Lernziele und Lernsitzungen mit CRUD und Status-Filter

## 1. Problem / Ziel

Das Grundgerüst (Projekt `learning_companion`, App `core`, Authentifizierung, Profil) steht. Es fehlt die eigentliche Fachlogik: Nutzer können bislang keine Lernziele erfassen und keine Lernzeit dokumentieren.

Dieses Ticket ergänzt zwei Entitäten:

1. **Goal** — ein Lernziel mit Titel, Beschreibung und Status (`planned` / `in-progress` / `done`).
2. **LearningSession** — eine einzelne Lernsitzung, die an genau ein Goal gebunden ist, mit Datum, Dauer in Minuten, Notizen und Tags.

Für beide Entitäten wird der vollständige CRUD-Zyklus (List, Create, Detail, Edit, Delete) bereitgestellt. Die Goals-Liste ist per Query-Parameter `?status=` nach Status filterbar.

Zentrale Anforderung ist die Mandantentrennung: **Jeder Nutzer sieht und bearbeitet ausschließlich seine eigenen Goals und Sessions.** Das gilt für jede der fünf CRUD-Operationen, für lesende wie schreibende Zugriffe, und muss durch Tests belegt sein — analog zum bereits umgesetzten Profil-Scoping.

## 2. Akzeptanzkriterien

**Datenmodell Goal**

- [ ] Es existiert ein Modell `Goal` mit den Feldern: `user` (ForeignKey auf `settings.AUTH_USER_MODEL`, `on_delete=CASCADE`), `title` (CharField, Pflichtfeld), `description` (TextField, optional), `status` (CharField mit `choices`), `created_at` (`auto_now_add`) und `updated_at` (`auto_now`).
- [ ] `status` erlaubt ausschließlich die Werte `planned`, `in-progress` und `done`; der Default beim Anlegen ist `planned`. Ein abweichender Wert wird von der Modell-Validierung (`full_clean()`) abgelehnt.
- [ ] `Goal.__str__()` liefert den Titel.

**Datenmodell LearningSession**

- [ ] Es existiert ein Modell `LearningSession` mit den Feldern: `goal` (ForeignKey auf `Goal`, `on_delete=CASCADE`, `related_name="sessions"`), `date` (DateField), `duration` (PositiveIntegerField, Minuten), `notes` (TextField, optional) und `tags` (Mehrfachauswahl, wiederverwendet das bestehende `Tag`-Modell).
- [ ] `duration` akzeptiert nur Werte größer als 0; eine Dauer von 0 oder ein negativer Wert wird von `full_clean()` abgelehnt.
- [ ] Das Löschen eines Goals löscht dessen Sessions mit (Test: nach `goal.delete()` ist `LearningSession.objects.filter(goal_id=<alte_id>).count() == 0`).
- [ ] `LearningSession.__str__()` liefert einen menschenlesbaren Wert aus Goal-Titel und Datum.

**CRUD-Views Goal**

- [ ] Für `Goal` existieren fünf erreichbare Views: Liste (`/goals/`), Anlegen (`/goals/new/`), Detail (`/goals/<pk>/`), Bearbeiten (`/goals/<pk>/edit/`) und Löschen (`/goals/<pk>/delete/`).
- [ ] Die Goals-Liste zeigt einem eingeloggten Nutzer mit Status 200 ausschließlich seine eigenen Goals; Goals anderer Nutzer tauchen weder im Kontext (`object_list`) noch im gerenderten HTML auf.
- [ ] Beim Anlegen wird das Goal automatisch dem eingeloggten Nutzer zugeordnet; das Feld `user` ist **nicht** Teil des Formulars und kann nicht per POST überschrieben werden (Test: ein POST mit zusätzlichem `user=<fremde_id>` legt das Goal dennoch auf dem eigenen Nutzer an).
- [ ] Bearbeiten und Löschen des eigenen Goals funktionieren und sind nach dem Vorgang in der Datenbank nachweisbar (geänderte Werte bzw. Datensatz entfernt).

**CRUD-Views LearningSession**

- [ ] Für `LearningSession` existieren fünf erreichbare Views: Liste, Anlegen, Detail, Bearbeiten und Löschen.
- [ ] Die Session-Liste zeigt einem eingeloggten Nutzer ausschließlich Sessions, deren Goal ihm gehört.
- [ ] Beim Anlegen einer Session stehen im Formularfeld `goal` ausschließlich die eigenen Goals zur Auswahl; ein POST mit der ID eines fremden Goals wird mit einem Formularfehler (Status 200) abgewiesen und legt **keine** Session an.

**Status-Filter**

- [ ] Der Aufruf `/goals/?status=planned` liefert ausschließlich Goals mit Status `planned`; analog für `in-progress` und `done`.
- [ ] Ohne `status`-Parameter liefert `/goals/` alle eigenen Goals.
- [ ] Ein ungültiger Wert (z. B. `/goals/?status=unsinn`) führt nicht zu einem Fehler (Status 200) und liefert alle eigenen Goals, als wäre kein Filter gesetzt.
- [ ] Der Filter wirkt ausschließlich innerhalb der eigenen Daten: `/goals/?status=done` zeigt keine fremden Goals mit Status `done`.

**Scoping und Zugriffskontrolle**

- [ ] Alle zehn CRUD-Views (fünf für Goal, fünf für LearningSession) leiten einen nicht eingeloggten Aufruf mit Status 302 auf die Login-Seite um.
- [ ] Nutzer A erhält beim Aufruf von Detail, Bearbeiten oder Löschen eines **fremden** Goals (Nutzer B) Status 404; die Daten von B erscheinen nicht in der Response.
- [ ] Ein POST von Nutzer A auf die Edit-URL eines fremden Goals ändert dessen Daten nicht (Nachweis per `refresh_from_db()` nach dem abgewiesenen Request).
- [ ] Ein POST von Nutzer A auf die Delete-URL eines fremden Goals löscht dieses nicht; das Goal von B existiert danach weiterhin.
- [ ] Die vier vorstehenden Scoping-Kriterien gelten gleichermaßen für `LearningSession` und sind dafür separat getestet.

**Tests und Regression**

- [ ] Automatisierte Tests in `core/tests/` decken ab: Modell-Validierung (Status-Choices, Dauer, Kaskadenlöschung), CRUD für beide Entitäten, den Status-Filter inkl. ungültigem Wert sowie das vollständige Scoping (A gegen B) für lesende und schreibende Zugriffe.
- [ ] Die bestehenden 17 Tests aus Feature 1 (Auth, Profil, Profil-Scoping) laufen unverändert weiter durch.
- [ ] `python manage.py check` und `python manage.py test` enden mit Exit-Code 0.
- [ ] Für `core` existiert eine neue, eingecheckte Migration; `python manage.py makemigrations --check --dry-run` meldet keine ausstehenden Änderungen.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Bestehender Stack unverändert: Python 3.12, Django 5.2, SQLite, serverseitig gerenderte Django-Templates, keine zusätzlichen Abhängigkeiten in `requirements.txt`.
- Beide Modelle werden in der bestehenden App `core` ergänzt; es wird **keine** neue App angelegt.
- `tags` auf `LearningSession` verwendet das bereits existierende `Tag`-Modell per `ManyToManyField` weiter — kein zweites Tag-Konzept, kein `ArrayField` (PostgreSQL-only).
- Das Scoping folgt dem im Profil-Feature etablierten Muster: `LoginRequiredMixin` plus ein `get_queryset()`, das generell auf `request.user` filtert. Ein fremder PK ergibt damit strukturell 404 statt einer nachgelagerten Berechtigungsprüfung.
- Die Zuordnung `user` wird serverseitig in `form_valid()` aus `request.user` gesetzt und ist nie Teil des Formulars.
- Der Status-Filter liest `request.GET.get("status")` und wird gegen die definierten Choices validiert; unbekannte Werte werden ignoriert statt zu einem Fehler zu führen.
- Löschen erfolgt über Django-`DeleteView` per POST mit Bestätigungsseite (kein Löschen per GET).
- `status` wird über `models.TextChoices` definiert, damit Choices, Labels und Validierung aus einer Quelle stammen.

**Out-of-Scope**

- Keine REST-API, kein Django REST Framework, kein JavaScript-Frontend.
- Keine Auswertungen, Statistiken, Diagramme oder Zeit-Aggregationen über Sessions.
- Kein Timer und keine laufende Zeiterfassung — `duration` wird manuell eingetragen.
- Keine Erinnerungen, Benachrichtigungen oder E-Mails.
- Kein Teilen von Goals zwischen Nutzern, keine Kollaboration, keine Sichtbarkeits-Einstellungen.
- Keine Pflege-Oberfläche für `Tag` im Frontend; Tags werden weiterhin über das Django-Admin angelegt.
- Keine Pagination und keine Sortier-Oberfläche auf den Listen; nur der geforderte Status-Filter.
- Kein individuelles UI-Design oder CSS-Framework; Styling bleibt minimal.
