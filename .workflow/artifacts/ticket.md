# Ticket: Resource Library — Lernressourcen an Goals anhängen, typisiert anzeigen und löschen

## 1. Problem / Ziel

Nutzer können Lernziele (`Goal`) anlegen und Lernsitzungen (`LearningSession`) dokumentieren. Was fehlt, ist der Ort für das Material: Artikel, Videos, Repositories und Dokumentationen, die zu einem Ziel gehören, liegen bislang außerhalb der Anwendung.

Dieses Ticket ergänzt eine Entität **Resource** mit URL, Titel und Typ, die an genau ein Goal gebunden ist. Der Arbeitsablauf soll ohne Seitenwechsel funktionieren:

1. Auf der Goal-Detailseite steht ein **Inline-Formular**, über das eine Ressource direkt angehängt wird.
2. Alle Ressourcen des Goals werden ebendort angezeigt, **nach Typ optisch hervorgehoben** (Badge).
3. Jede Ressource lässt sich von dort aus **löschen**.

Zentrale Anforderung bleibt die Mandantentrennung: Ressourcen hängen an Goals, Goals gehören Nutzern. Ein Nutzer darf Ressourcen **ausschließlich an eigene Goals anhängen** und **ausschließlich Ressourcen eigener Goals löschen oder sehen**. Der Besitz wird dabei nicht am Resource-Objekt gespeichert, sondern über die Kette `resource → goal → user` aufgelöst — analog zum bereits umgesetzten Session-Scoping.

## 2. Akzeptanzkriterien

**Datenmodell Resource**

- [ ] Es existiert ein Modell `Resource` mit den Feldern: `goal` (ForeignKey auf `Goal`, `on_delete=CASCADE`, `related_name="resources"`), `url` (URLField, Pflichtfeld), `title` (CharField, Pflichtfeld), `type` (CharField mit `choices`) und `created_at` (`auto_now_add`).
- [ ] `type` erlaubt ausschließlich die Werte `article`, `video`, `repo` und `doc`; der Default beim Anlegen ist `article`. Ein abweichender Wert wird von `full_clean()` abgelehnt.
- [ ] `url` wird validiert: eine Eingabe ohne gültiges Schema (z. B. `"kein-link"`) wird von `full_clean()` mit einem Fehler auf dem Feld `url` abgelehnt.
- [ ] Das Löschen eines Goals löscht dessen Ressourcen mit (Test: nach `goal.delete()` ist `Resource.objects.filter(goal_id=<alte_id>).count() == 0`).
- [ ] `Resource.__str__()` liefert den Titel.

**Inline-Formular auf der Goal-Detailseite**

- [ ] Die Goal-Detailseite (`/goals/<pk>/`) enthält ein Formular zum Anhängen einer Ressource mit den Feldern `url`, `title` und `type` sowie `{% csrf_token %}`. Das Feld `goal` ist **nicht** Teil des Formulars.
- [ ] Ein POST mit gültigen Daten auf die Anlege-URL legt die Ressource am adressierten Goal an und leitet per Redirect (Status 302) zurück auf die Goal-Detailseite; die neue Ressource ist dort anschließend sichtbar.
- [ ] Ein POST mit ungültigen Daten (z. B. leerer Titel oder ungültige URL) legt **keine** Ressource an und zeigt die Fehler mit Status 200 sichtbar an, ohne die bereits vorhandenen Ressourcen des Goals zu verlieren.
- [ ] Das Goal wird ausschließlich aus der URL bzw. serverseitig aus dem gescopten Queryset bestimmt und ist nicht per POST-Feld überschreibbar (Test: ein POST mit zusätzlichem `goal=<fremde_id>` hängt die Ressource dennoch an das adressierte eigene Goal).

**Anzeige mit Typ-Badge**

- [ ] Die Goal-Detailseite listet alle Ressourcen des Goals mit Titel und verlinkter URL.
- [ ] Zu jeder Ressource wird der Typ als lesbares Label angezeigt (`Artikel`, `Video`, `Repository`, `Dokumentation`), nicht als technischer Wert.
- [ ] Jede Ressource trägt eine typabhängige CSS-Klasse der Form `badge-<type>` (z. B. `badge-video`), über die die optische Hervorhebung erfolgt; der Test prüft, dass die zum Typ passende Klasse im gerenderten HTML vorkommt.
- [ ] Hat ein Goal keine Ressourcen, erscheint ein entsprechender Hinweistext statt einer leeren Liste.
- [ ] Ressourcen fremder Goals erscheinen nicht auf der eigenen Goal-Detailseite.

**Löschen von Ressourcen**

- [ ] Es existiert eine Lösch-Route für Ressourcen, die ausschließlich per POST löscht; ein GET löscht nicht.
- [ ] Ein POST auf die Lösch-URL einer Ressource an einem **eigenen** Goal entfernt den Datensatz und leitet zurück auf die zugehörige Goal-Detailseite.
- [ ] Nach dem Löschen bleibt das Goal selbst unverändert bestehen.

**Scoping und Zugriffskontrolle**

- [ ] Anlegen und Löschen von Ressourcen leiten einen nicht eingeloggten Aufruf mit Status 302 auf die Login-Seite um.
- [ ] Ein POST von Nutzer A auf die Anlege-URL eines **fremden** Goals (Nutzer B) liefert Status 404 und legt **keine** Ressource an (Nachweis: `Resource.objects.count()` unverändert).
- [ ] Ein POST von Nutzer A auf die Lösch-URL einer Ressource von Nutzer B liefert Status 404; die Ressource von B existiert danach weiterhin.
- [ ] Ein GET von Nutzer A auf die Detailseite eines fremden Goals liefert weiterhin Status 404 — die Ressourcen von B werden dabei nicht ausgegeben.
- [ ] Zur Gegenprobe ist belegt, dass Anlegen und Löschen am **eigenen** Goal weiterhin funktionieren; die 404-Kriterien sind damit nicht durch eine global gesperrte View trivial erfüllbar.

**Tests und Regression**

- [ ] Automatisierte Tests in `core/tests/` decken ab: Modell-Validierung (Typ-Choices, URL-Format, Kaskadenlöschung), das Inline-Anlegen (Erfolg und Fehlerfall), die Anzeige inklusive Badge-Klasse sowie das vollständige Scoping für Anlegen, Löschen und Anzeigen.
- [ ] Die bestehenden 63 Tests aus Feature 1 und 2 laufen unverändert weiter durch.
- [ ] `python manage.py check` und `python manage.py test` enden mit Exit-Code 0.
- [ ] Für `core` existiert eine neue, eingecheckte Migration; `python manage.py makemigrations --check --dry-run` meldet keine ausstehenden Änderungen.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Bestehender Stack unverändert: Python 3.12, Django 5.2, SQLite, serverseitig gerenderte Django-Templates, **keine** zusätzlichen Abhängigkeiten in `requirements.txt`.
- Das Modell wird in der bestehenden App `core` ergänzt; keine neue App.
- `type` wird über `models.TextChoices` definiert, damit Werte, Labels und Validierung aus einer Quelle stammen — wie bereits bei `Goal.Status`.
- Der Besitz einer Ressource wird **nicht** redundant gespeichert, sondern immer über `goal__user` aufgelöst. Damit können Goal und Ressource nicht auseinanderlaufen.
- Das Scoping folgt dem etablierten Muster: `LoginRequiredMixin` plus ein `get_queryset()`, das generell auf `request.user` filtert. Ein fremder PK ergibt strukturell 404 statt einer nachgelagerten Berechtigungsprüfung.
- Beim Anlegen wird das Ziel-Goal über `get_object_or_404()` aus dem auf `request.user` gescopten Goal-Queryset bestimmt — nicht aus einem Formularfeld.
- Die Goal-Detailseite bleibt eine `DetailView`; das Inline-Formular wird über `get_context_data()` bereitgestellt und von einer separaten View verarbeitet. Bei Validierungsfehlern wird die Detailseite mit dem fehlerbehafteten Formular erneut gerendert (Status 200).
- Die Badges werden über CSS-Klassen im bestehenden minimalen Styling umgesetzt; es wird kein CSS-Framework eingeführt.
- Gelöscht wird ausschließlich per POST mit CSRF-Token (kein Löschen per GET).

**Out-of-Scope**

- Keine REST-API, kein Django REST Framework, kein JavaScript — das Inline-Formular ist ein normales HTML-Formular mit vollem Seiten-Reload, kein AJAX.
- Kein Bearbeiten bestehender Ressourcen (nur Anlegen, Anzeigen, Löschen).
- Keine eigenständige Ressourcen-Übersichtsseite über alle Goals hinweg.
- Kein automatisches Auslesen von Titel, Favicon oder Metadaten aus der URL; kein Abruf der Ziel-URL durch den Server.
- Keine Prüfung auf Erreichbarkeit der URL und keine Dublettenerkennung.
- Keine Verknüpfung von Ressourcen mit `LearningSession` oder `Tag`.
- Keine Sortier- oder Filteroberfläche für Ressourcen, keine Pagination.
- Kein individuelles UI-Design oder CSS-Framework; Styling bleibt minimal.
