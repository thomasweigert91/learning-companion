# Code Review: Resource Library — Inline-Anlegen, Typ-Badges und Löschen

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, **90 Tests** (63 aus Feature 1 und 2 + 27 neue), `validate_code.ps1` grün.

---

## 1. Abdeckung der Akzeptanzkriterien

### Datenmodell Resource

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `Resource` mit `goal`/`url`/`title`/`type`/`created_at` | `core/models.py:115-146` | ja |
| 2 | Nur `article`/`video`/`repo`/`doc`, Default `article`, `full_clean()` lehnt ab | `test_default_type_is_article`, `test_all_four_types_are_valid`, `test_invalid_type_rejected_by_full_clean` | ja |
| 3 | URL-Validierung, `"kein-link"` → Fehler auf `url` | `test_invalid_url_rejected_by_full_clean` | ja |
| 4 | Löschen des Goals kaskadiert | `test_deleting_goal_cascades_to_resources` | ja |
| 5 | `__str__` liefert Titel | `test_resource_str_returns_title` | ja |

### Inline-Formular auf der Goal-Detailseite

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 6 | Formular mit `url`/`title`/`type` und CSRF-Token, ohne `goal` | `test_goal_detail_contains_resource_form`; `ResourceForm.Meta.fields` | ja |
| 7 | Gültiger POST → 302 zurück auf die Detailseite, Ressource sichtbar | `test_create_resource_redirects_to_goal_detail`, `test_create_resource_appears_on_detail_page` | ja |
| 8 | Ungültiger POST → 200 mit Fehlern, nichts angelegt, vorhandene Ressourcen bleiben sichtbar | `test_create_resource_with_invalid_url_shows_errors`, `test_create_resource_with_empty_title_shows_errors`, `test_invalid_post_keeps_existing_resources_visible` | ja |
| 9 | Goal nicht per POST überschreibbar | `test_goal_field_in_post_is_ignored` | ja |

### Anzeige mit Typ-Badge

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 10 | Liste mit Titel und verlinkter URL | `core/templates/core/_resource_list.html:7-8` | ja |
| 11 | Lesbares Label statt technischem Wert | `test_resource_type_label_is_human_readable` (prüft `"Repository"`) | ja |
| 12 | Typabhängige CSS-Klasse `badge-<type>` | `test_resource_badge_class_matches_type` (`subTest` über alle vier Typen) | ja |
| 13 | Hinweistext bei leerer Liste | `test_empty_resource_list_shows_hint` | ja |
| 14 | Keine fremden Ressourcen auf der eigenen Seite | `test_foreign_resources_not_on_own_goal_detail` | ja |

### Löschen

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 15 | Nur per POST; GET löscht nicht | `test_delete_requires_post` | ja |
| 16 | POST entfernt und leitet auf die Goal-Detailseite | `test_delete_resource_removes_it_and_redirects` | ja |
| 17 | Goal bleibt bestehen | `test_delete_resource_keeps_goal` | ja |

### Scoping und Zugriffskontrolle

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 18 | Anlegen und Löschen erfordern Login | `test_resource_create_requires_login`, `test_resource_delete_requires_login` | ja |
| 19 | POST auf fremdes Goal → 404, nichts angelegt | `test_cannot_add_resource_to_foreign_goal` (prüft Status **und** `Resource.objects.count()`) | ja |
| 20 | POST auf fremde Ressource → 404, bleibt bestehen | `test_cannot_delete_foreign_resource` | ja |
| 21 | Fremde Goal-Detailseite → 404, keine Ressourcen ausgegeben | `test_foreign_goal_detail_still_404`, `test_cannot_get_delete_page_of_foreign_resource` | ja |
| 22 | Gegenprobe: eigenes Anlegen und Löschen funktioniert | `test_own_resource_create_and_delete_work` | ja |

### Tests und Regression

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 23 | Tests decken Modell, Anlegen, Anzeige, Scoping ab | `test_resources.py` (21), `test_resource_scoping.py` (8) | ja |
| 24 | Die 63 Tests aus Feature 1 und 2 laufen unverändert weiter | 90 gesamt, kein bestehendes Testmodul angefasst | ja |
| 25 | `check` und `test` Exit-Code 0; Migration eingecheckt, `--check --dry-run` sauber | Hook grün; `core/migrations/0003_resource.py`; "No changes detected" | ja |

**25 von 25 Kriterien erfüllt.**

## 2. Sicherheit

**Auth-Bypass — geprüft, kein Befund.**

Beide Schreibpfade sind auf unterschiedliche, aber gleichwertige Weise abgesichert:

- **Anlegen:** `ResourceCreateView.post()` holt das Ziel-Goal per `get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)`. Der 404 fällt also, **bevor** das Formular überhaupt gebunden wird — es gibt keinen Pfad, auf dem erst geschrieben und dann geprüft würde. `test_cannot_add_resource_to_foreign_goal` prüft deshalb bewusst Status **und** `Resource.objects.count()`.
- **Löschen:** `ResourceDeleteView.get_queryset()` filtert auf `goal__user=request.user`. Ein fremder PK ist im Queryset nicht enthalten und ergibt in `get_object()` automatisch 404 — für GET (Bestätigungsseite) wie für POST. Beide Fälle sind separat getestet.

**Massenzuweisung auf `goal` ausgeschlossen.** `ResourceForm.Meta.fields` enthält `goal` nicht; die Bindung setzt die View aus dem URL-PK gegen das gescopte Queryset. `test_goal_field_in_post_is_ignored` schickt gezielt ein abweichendes `goal` mit und belegt, dass die Ressource am adressierten Goal landet.

**Keine SSRF-Fläche.** Die URL wird gespeichert und als Link ausgegeben, aber **nie vom Server abgerufen** — kein Metadaten-Scraping, kein Favicon-Fetch (im Ticket explizit Out-of-Scope). Damit entfällt die Angriffsklasse, bei der ein Nutzer den Server über eine eingetragene URL gegen interne Adressen laufen lässt.

**XSS.** Titel und URL werden über das Django-Template-Autoescaping ausgegeben; kein `|safe`, kein `mark_safe`, kein `format_html` mit Nutzereingaben. Die externen Links tragen `rel="noopener noreferrer"` bei `target="_blank"` — damit kann die Zielseite nicht über `window.opener` auf die aufrufende Seite zugreifen.

**URL-Schema.** `URLField` lässt per Default `http` und `https` zu; `javascript:` wird vom `URLValidator` abgelehnt. Ein `javascript:`-Link im `href` ist damit nicht einschleusbar.

**CSRF.** Inline-Formular, Lösch-Formulare in der Liste und die Bestätigungsseite tragen alle `{% csrf_token %}`. Gelöscht wird ausschließlich per POST.

**Kein Information Leak.** Fremde Objekte liefern durchgängig 404 statt 403; aus der Antwort ist nicht ableitbar, ob eine ID überhaupt existiert.

## 3. Behobener Fehler während der Umsetzung

Der erste Testlauf meldete drei Fehlschläge mit **405 statt 200** auf dem Fehlerpfad des Inline-Formulars (`test_create_resource_with_invalid_url_shows_errors`, `test_create_resource_with_empty_title_shows_errors`, `test_invalid_post_keeps_existing_resources_visible`).

Ursache: Die Fehlerbehandlung reichte den POST per `GoalDetailView.as_view(...)(request, pk=pk)` an die Detailseite weiter. `DetailView` erlaubt in `http_method_names` aber nur GET und lehnte den POST im `dispatch()` mit 405 ab.

Behoben in `ResourceCreateView.render_detail_with_errors()`: Die Detailseite wird nicht erneut dispatcht, sondern ihr Kontext direkt wiederverwendet (`setup()` → `object` setzen → `render_to_response(get_context_data(...))`). Damit bleibt der Dispatch-Zyklus außen vor, beide Pfade teilen sich aber weiterhin eine Kontext-Quelle — der Fehlerfall divergiert also nicht, falls die Detailseite später um Kontext wächst. Nach der Korrektur 90/90 grün.

## 4. Formatierung und tote Code-Pfade

Imports sortiert und vollständig genutzt, keine auskommentierten Reste, Namensgebung konsistent zu den Vorfeatures (`resource_create`, `resource_delete`). Beide neuen Templates werden referenziert, beide neuen URL-Namen aus Templates und Tests aufgelöst. `manage.py check` meldet 0 Issues.

Eine Stelle, die bewusst so aussieht: `ResourceCreateView` implementiert nur `post()` und erbt von `View` statt von `CreateView`. Das ist korrekt — das Formular lebt auf der Goal-Detailseite, ein GET auf die Anlege-URL hätte keinen eigenen Zweck. Ein `CreateView` hätte ein nie gerendertes Template und eine ungenutzte GET-Route mitgebracht.

## 5. Abweichungen vom Plan

| Abweichung | Begründung |
|---|---|
| `core/templates/core/resource_confirm_delete.html` zusätzlich angelegt | Im Plan unter Schritt 5 erwähnt, in der Dateiliste von Abschnitt 1 aber nicht aufgeführt. Nötig, weil `DeleteView` bei GET eine Bestätigungsseite rendert — ohne Template hätte der GET-Pfad einen `TemplateDoesNotExist` geworfen. |
| Fehlerpfad über `render_detail_with_errors()` statt `as_view()`-Aufruf | Der im Plan skizzierte Weg war nicht lauffähig (405, siehe Abschnitt 3). Die Lösung erfüllt dieselbe Absicht — eine Kontext-Quelle für beide Pfade. |
| 27 statt der ~24 geplanten neuen Tests | Drei Ergänzungen: `test_all_four_types_are_valid`, `test_delete_resource_keeps_goal` und die anonymen Zugriffstests prüfen zusätzlich, dass tatsächlich nichts geschrieben bzw. gelöscht wurde, nicht nur den Redirect. |

Keine Abweichung bei Modellfeldern, Routen oder Scoping-Logik.

## 6. Fazit

Alle 25 Akzeptanzkriterien sind erfüllt und durch benannte Tests oder Kommando-Exit-Codes belegt. Der Besitz wird konsequent über `goal__user` aufgelöst statt am Resource-Objekt dupliziert, womit Goal und Ressource nicht auseinanderlaufen können. Die drei kritischen Stellen dieser Feature-Art — fremdes Goal beim Anlegen, fremde Ressource beim Löschen, Überschreiben des Fremdschlüssels per POST — sind gezielt geschlossen und einzeln getestet. Ein während der Umsetzung aufgetretener 405-Fehler auf dem Fehlerpfad wurde gefunden, behoben und erneut verifiziert. Keine offenen Sicherheitsbefunde, keine toten Pfade, keine Regression in den Vorfeatures.

**Status: APPROVED**
