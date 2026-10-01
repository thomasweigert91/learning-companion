# Implementierungs-Plan: Resource Library — Inline-Anlegen, Typ-Badges und Löschen

## 1. Betroffene Dateien

**Ändern**

- Ändern: `core/models.py` — Modell `Resource` ergänzen
- Ändern: `core/forms.py` — `ResourceForm` ergänzen
- Ändern: `core/views.py` — `GoalDetailView` um das Inline-Formular erweitern, `ResourceCreateView` und `ResourceDeleteView` ergänzen
- Ändern: `core/urls.py` — zwei Routen ergänzen
- Ändern: `core/admin.py` — `Resource` registrieren
- Ändern: `core/templates/core/goal_detail.html` — Ressourcen-Liste mit Badges, Inline-Formular, Lösch-Buttons
- Ändern: `core/templates/base.html` — minimales Badge-Styling im `<head>`

**Neu**

- Neu: `core/migrations/0003_resource.py` (per `makemigrations` erzeugt, eingecheckt)
- Neu: `core/templates/core/_resource_list.html` — Teil-Template für die Ressourcen-Liste inkl. Badge und Lösch-Formular
- Neu: `core/tests/test_resources.py` — Modell, Anlegen, Anzeige und Badge
- Neu: `core/tests/test_resource_scoping.py` — Mandantentrennung A gegen B

**Unverändert:** `learning_companion/settings.py`, `requirements.txt`, `core/signals.py`, `core/apps.py` sowie alle bestehenden Testmodule aus Feature 1 und 2.

## 2. Datenmodelle & Migrationen

### `Resource` (`core/models.py`)

Typ über `models.TextChoices`, konsistent zu `Goal.Status`:

```python
class Type(models.TextChoices):
    ARTICLE = "article", "Artikel"
    VIDEO = "video", "Video"
    REPO = "repo", "Repository"
    DOC = "doc", "Dokumentation"
```

| Feld | Typ | Optionen |
| --- | --- | --- |
| `goal` | `ForeignKey` | `Goal`, `on_delete=models.CASCADE`, `related_name="resources"` |
| `url` | `URLField` | `max_length=500` |
| `title` | `CharField` | `max_length=200` |
| `type` | `CharField` | `max_length=20`, `choices=Type.choices`, `default=Type.ARTICLE` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

- `Meta.ordering = ["-created_at", "-pk"]`
- `__str__` → `self.title`

Zur Validierung: `URLField` bringt den `URLValidator` mit, der in `full_clean()` greift und `"kein-link"` mit einem Fehler auf `url` ablehnt. `max_length=500` statt der Default-200, weil Doku- und Repo-Links mit Ankern und Query-Parametern schnell lang werden. Die `choices`-Validierung auf `type` leistet ebenfalls `full_clean()`.

Der Besitz wird **nicht** am Modell gespeichert, sondern immer über `goal__user` aufgelöst — identisch zur Lösung bei `LearningSession`. Die Kaskade beim Löschen eines Goals kommt aus `on_delete=models.CASCADE`.

### Migration

- `python manage.py makemigrations core` erzeugt `0003_resource.py` (eine `CreateModel`-Operation).
- Danach `python manage.py migrate`.
- Keine Datenmigration: die Tabelle ist neu, bestehende Daten bleiben unberührt.
- Abschließend `makemigrations --check --dry-run` als Nachweis der Deckungsgleichheit.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Modell und Migration** — `Resource` inkl. innerer `Type`-TextChoices-Klasse, `__str__` und `Meta.ordering` in `core/models.py` ergänzen; `core/admin.py` um `ResourceAdmin` erweitern (`list_display` mit Titel, Goal und Typ, `list_filter` auf `type`, `search_fields` auf Titel und URL). Dann `makemigrations core` und `migrate`. Abnahme: `manage.py check` Exit-Code 0, `0003_resource.py` existiert.

- [ ] **Schritt 2: Formular** — `ResourceForm(ModelForm)` in `core/forms.py` mit `fields = ["url", "title", "type"]`. Das Feld `goal` ist bewusst **nicht** enthalten: Das Ziel-Goal bestimmt die View aus der URL gegen das gescopte Queryset, damit es nicht per POST überschreibbar ist. Deutsche Labels und ein `URLInput`-Widget mit Platzhalter.

- [ ] **Schritt 3: Inline-Formular in der Goal-Detailseite** — `GoalDetailView.get_context_data()` legt `resource_form` in den Kontext. Damit der Fehlerfall das ausgefüllte Formular zurückgeben kann, ohne die Detailseite zu duplizieren, bekommt die View ein optionales Attribut: Ist `self.resource_form` bereits gesetzt (von der Create-View bei Validierungsfehlern), wird dieses verwendet, sonst ein frisches `ResourceForm()`. Die Ressourcen selbst kommen über `goal.resources.all` direkt aus der Beziehung.

- [ ] **Schritt 4: `ResourceCreateView`** — Eine schlanke `View` mit `LoginRequiredMixin`, die ausschließlich `post()` implementiert (ein GET auf die Anlege-URL hat keinen eigenen Zweck, das Formular lebt auf der Detailseite). Ablauf:
  1. Ziel-Goal per `get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)` holen — ein fremder PK ergibt damit 404, bevor irgendetwas geschrieben wird.
  2. `ResourceForm(request.POST)` binden; bei `is_valid()` `form.instance.goal = goal` setzen, speichern und per `redirect()` auf `goal.get_absolute_url()` zurückleiten (Status 302).
  3. Bei Fehlern die Goal-Detailseite mit dem fehlerbehafteten Formular erneut rendern (Status 200), indem `GoalDetailView` mit gesetztem `resource_form` aufgerufen wird. Die bereits vorhandenen Ressourcen bleiben dadurch sichtbar.
  
  Weil `goal` kein Formularfeld ist und das Goal aus dem gescopten Queryset stammt, ist ein mitgeschicktes `goal=<fremde_id>` im POST wirkungslos.

- [ ] **Schritt 5: `ResourceDeleteView`** — `DeleteView` mit `LoginRequiredMixin` und `get_queryset()` → `Resource.objects.filter(goal__user=self.request.user).select_related("goal")`. Ein fremder PK ist im Queryset nicht enthalten und ergibt in `get_object()` automatisch 404 — für GET (Bestätigungsseite) wie POST (Löschen). `get_success_url()` liefert `self.object.goal.get_absolute_url()`, führt also zurück auf die Goal-Detailseite. Da Django beim Löschen `self.object` vor dem Redirect auflöst, wird das Goal in `select_related` mitgeladen.
  
  Gelöscht wird nur per POST; das bringt `DeleteView` von Haus aus mit. Eine eigene Bestätigungsseite ist nötig, weil ein GET sonst ins Leere liefe — `core/templates/core/resource_confirm_delete.html`.

- [ ] **Schritt 6: URLs** — `core/urls.py` um zwei Routen erweitern:
  - `goals/<int:pk>/resources/add/` → `ResourceCreateView`, Name `resource_create` (der PK adressiert das **Goal**).
  - `resources/<int:pk>/delete/` → `ResourceDeleteView`, Name `resource_delete` (der PK adressiert die **Resource**).

- [ ] **Schritt 7: Templates** — `goal_detail.html` bekommt einen Abschnitt "Ressourcen", der das Teil-Template `_resource_list.html` einbindet, sowie darunter das Inline-Formular (POST auf `core:resource_create` mit `{% csrf_token %}`, sichtbare `{{ resource_form.errors }}`). `_resource_list.html` rendert je Ressource: Titel als Link auf `resource.url` (mit `rel="noopener noreferrer"` und `target="_blank"`), ein `<span class="badge badge-{{ resource.type }}">{{ resource.get_type_display }}</span>` sowie ein POST-Formular mit Lösch-Button. Bei leerer Liste ein Hinweistext. In `base.html` kommt ein kleiner `<style>`-Block mit den vier `badge-*`-Klassen (unterschiedliche Hintergrundfarben) — bewusst minimal, kein CSS-Framework.
  
  Zur Badge-Klasse: Sie wird direkt aus `resource.type` gebildet, das Label separat über `get_type_display`. Damit erfüllt ein Template beide Kriterien (technische Klasse für die Optik, lesbares Label für den Text), ohne eine Zuordnungstabelle im Template zu pflegen.

- [ ] **Schritt 8: Tests** — Die beiden neuen Testmodule gemäß Abschnitt 4 schreiben.

- [ ] **Schritt 9: Gesamtvalidierung** — `manage.py check`, `makemigrations --check --dry-run`, `manage.py test` (63 bestehende plus neue) und `.\.workflow\hooks\validate_code.ps1`; alles mit Exit-Code 0.

## 4. Validierung & Test-Strategie

### `core/tests/test_resources.py`

Modell:

- `test_resource_str_returns_title`
- `test_default_type_is_article` — ohne `type` angelegt → `article`.
- `test_all_four_types_are_valid` — `full_clean()` wirft für keinen der vier Werte.
- `test_invalid_type_rejected_by_full_clean` — `type="podcast"` → `ValidationError` mit Schlüssel `type`.
- `test_invalid_url_rejected_by_full_clean` — `url="kein-link"` → `ValidationError` mit Schlüssel `url`.
- `test_deleting_goal_cascades_to_resources` — nach `goal.delete()` ist `Resource.objects.filter(goal_id=alte_id).count() == 0`.

Inline-Anlegen:

- `test_goal_detail_contains_resource_form` — die Detailseite liefert `resource_form` im Kontext und enthält ein `csrfmiddlewaretoken`.
- `test_create_resource_redirects_to_goal_detail` — gültiger POST → 302 auf die Goal-Detailseite, Ressource am richtigen Goal.
- `test_create_resource_appears_on_detail_page` — nach dem Anlegen ist der Titel auf der Detailseite sichtbar.
- `test_create_resource_with_invalid_url_shows_errors` — Status 200, `"url"` in den Formularfehlern, `Resource.objects.count()` unverändert.
- `test_create_resource_with_empty_title_shows_errors` — Status 200, `"title"` in den Fehlern, nichts angelegt.
- `test_invalid_post_keeps_existing_resources_visible` — ein fehlerhafter POST darf die bereits vorhandenen Ressourcen auf der Seite nicht verschwinden lassen.
- `test_goal_field_in_post_is_ignored` — POST mit zusätzlichem `goal=<pk_eines_anderen_eigenen_goals>` → die Ressource hängt am Goal aus der URL.

Anzeige und Badge:

- `test_resource_badge_class_matches_type` — für jeden der vier Typen (`subTest`) prüfen, dass `badge-<type>` im HTML vorkommt.
- `test_resource_type_label_is_human_readable` — `"Repository"` erscheint, nicht `"repo"`.
- `test_empty_resource_list_shows_hint` — Goal ohne Ressourcen → Hinweistext, kein leeres Listengerüst.

Löschen:

- `test_delete_resource_removes_it_and_redirects` — POST → Redirect auf die Goal-Detailseite, Datensatz weg.
- `test_delete_resource_keeps_goal` — das Goal existiert nach dem Löschen der Ressource weiterhin.
- `test_delete_requires_post` — GET auf die Lösch-URL liefert 200 (Bestätigung) und löscht nicht.

### `core/tests/test_resource_scoping.py`

Zwei Nutzer A und B, je ein Goal mit je einer Ressource.

Anonymer Zugriff:

- `test_resource_create_requires_login` — POST ohne Login → `assertRedirects` auf `/accounts/login/?next=...`.
- `test_resource_delete_requires_login` — analog.

Fremdzugriff:

- `test_cannot_add_resource_to_foreign_goal` — A postet auf die Anlege-URL von B's Goal → Status 404 **und** `Resource.objects.count()` unverändert. Beides zusammen, weil ein 404 allein nicht belegt, dass nichts geschrieben wurde.
- `test_cannot_delete_foreign_resource` — A postet auf die Lösch-URL von B's Ressource → 404, und `Resource.objects.filter(pk=b_resource.pk).exists()` ist weiterhin `True`.
- `test_cannot_get_delete_page_of_foreign_resource` — GET auf dieselbe URL → 404, Titel von B nicht in der Response.
- `test_foreign_goal_detail_still_404` — A ruft B's Goal-Detailseite auf → 404; die Ressource von B wird nicht ausgegeben.
- `test_foreign_resources_not_on_own_goal_detail` — auf A's eigener Detailseite taucht B's Ressourcentitel nicht auf.

Gegenprobe:

- `test_own_resource_create_and_delete_work` — A legt am eigenen Goal an und löscht wieder; beides erfolgreich. Ohne diesen Test wären die 404-Kriterien auch durch eine global kaputte View erfüllt.

### Testdaten

- `setUpTestData` legt je Testklasse die nötigen Nutzer, Goals und Ressourcen an; Profile entstehen weiterhin automatisch per Signal.
- URLs in Testdaten sind valide (`https://example.com/...`), ungültige Werte nur dort, wo gezielt die Validierung geprüft wird.
- Keine Fixture-Dateien, keine neuen Abhängigkeiten.

### Auszuführende Kommandos

```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

### Definition of Done

Alle vier Kommandos enden mit Exit-Code 0, die 63 Tests aus Feature 1 und 2 laufen unverändert mit durch, `core/migrations/0003_resource.py` ist eingecheckt, und jedes der 25 Akzeptanzkriterien aus `.workflow/artifacts/ticket.md` ist durch mindestens einen benannten Test oder einen Kommando-Exit-Code belegt.
