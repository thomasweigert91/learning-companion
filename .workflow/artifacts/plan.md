# Implementierungs-Plan: UI- und Styling-Upgrade auf Bootstrap 5

## 1. Betroffene Dateien

**Neu**

- Neu: `core/templatetags/__init__.py`
- Neu: `core/templatetags/ui.py` (Filter `bs_widget`, `has_required`, Inclusion-Tag `nav_link`)
- Neu: `core/templates/core/_form.html` (generisches Formular-Partial)
- Neu: `core/templates/core/_nav_link.html` (Template des Nav-Link-Tags)
- Neu: `core/templates/core/_status_badge.html` (Status → Badge-Farbe)
- Neu: `core/templates/core/_home_card.html` (Schnellzugriffs-Card der Startseite)
- Neu: `core/tests/test_ui.py`

**Ändern**

- Ändern: `core/templates/base.html` (CDN, Navbar, Dropdown, Alerts, Skip-Link; Alt-CSS entfernen)
- Ändern: `core/templates/core/home.html`
- Ändern: `core/templates/registration/login.html`
- Ändern: `core/templates/registration/register.html`
- Ändern: `core/templates/core/profile_detail.html`
- Ändern: `core/templates/core/profile_form.html`
- Ändern: `core/templates/core/dashboard.html`
- Ändern: `core/templates/core/goal_list.html`
- Ändern: `core/templates/core/goal_detail.html`
- Ändern: `core/templates/core/goal_form.html`
- Ändern: `core/templates/core/goal_confirm_delete.html`
- Ändern: `core/templates/core/_resource_list.html`
- Ändern: `core/templates/core/resource_confirm_delete.html`
- Ändern: `core/templates/core/learningsession_list.html`
- Ändern: `core/templates/core/learningsession_detail.html`
- Ändern: `core/templates/core/learningsession_form.html`
- Ändern: `core/templates/core/learningsession_confirm_delete.html`
- Ändern: `core/views.py` (nur `SessionListView.get_queryset`: `prefetch_related("tags")`)
- Ändern: `requirements.txt` (Django-Pin `>=5.2`, siehe Schritt 1)

Damit sind **alle 17** bestehenden Templates erfasst.

## 2. Datenmodelle & Migrationen

**Keine.** Modelle, Formulare (`forms.py`) und URLs bleiben unverändert; es
entsteht keine Migration. `makemigrations --check --dry-run` muss weiterhin
"No changes detected" melden.

**Vom Redesign unberührte Verträge** (Grundlage der Regressionsfreiheit):

| Vertrag | Wo geprüft | Wie gesichert |
|---|---|---|
| Feld-IDs `id_<feld>` und Feldnamen | Auth-, Goal-, Session-, Resource-Tests (POSTs) | Widgets werden weiter von Django gerendert (`BoundField.as_widget`), nur `class`/ARIA-Attribute kommen hinzu |
| `id="status"` im Goal-Filter | Filter-Tests per GET-Parameter | ID unverändert übernommen |
| CSS-Klasse `badge-{typ}` | `test_resource_badge_class_matches_type` | bleibt als Zusatzklasse neben `badge` |
| `href="/dashboard/"` in der Navbar | `test_navbar_enthaelt_dashboard_link` | `nav_link`-Tag rendert `reverse()`-Ergebnis |
| "Fortschrittszusammenfassung" / "Naechste Lernschritte" nur mit Ergebnis | `test_ai_views` (Abwesenheit) | Wörter erscheinen ausschließlich in den `{% if %}`-Blöcken, nicht in Buttons oder Hilfetexten |
| Leerzustands-Texte Dashboard, Ressourcen | `test_dashboard`, `test_resources` | wortgleich übernommen |

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Setup -- Template-Tags** (`core/templatetags/ui.py`)

      ```python
      @register.filter
      def bs_widget(bound_field):
          """Rendert das Widget mit Bootstrap-Klasse und ARIA-Verknüpfungen."""
      ```
      - Klasse nach `bound_field.widget_type`:
        `checkbox`/`checkboxselectmultiple`/`radioselect` → `form-check-input`,
        `select`/`selectmultiple`/`nullbooleanselect` → `form-select`,
        sonst `form-control`. Vorhandene Klassen aus `widget.attrs` bleiben erhalten.
      - Bei Fehlern zusätzlich `is-invalid`.
      - `aria-invalid` und `aria-describedby` erzeugt **Django 5.2 selbst**
        (`BoundField.aria_describedby`) nach der Konvention `<auto_id>_helptext`
        und `<auto_id>_error`. Der Filter dupliziert das nicht; `_form.html`
        vergibt an Hilfe- und Fehlertext genau diese IDs. Weil das erst ab 5.2
        gilt (5.0/5.1 verknüpfen nur den Hilfetext), wird der Pin in
        `requirements.txt` von `Django>=5.0` auf `Django>=5.2` angehoben --
        installiert ist bereits 5.2.17 (LTS).
      - Rückgabe über `bound_field.as_widget(attrs=...)` -- ID, Name, Wert und
        `required` kommen damit unverändert von Django.

      `has_required(form)` → `True`, wenn ein sichtbares Feld Pflicht ist (steuert
      den Pflichtfeld-Hinweis).

      `nav_link(context, url_name, label, icon, section)` als Inclusion-Tag:
      ermittelt aus `request.resolver_match.url_name` den aktiven Bereich
      (`dashboard`; `goal*`/`resource*` → `goals`; `session*` → `sessions`;
      `profile*` → `profile`) und rendert `core/_nav_link.html` mit `active` +
      `aria-current="page"` für den passenden Link.

- [ ] **Schritt 2: Partials**

      `core/_form.html` -- erwartet `form`, optional `error_intro`:
      1. Fehler-Alert (`alert-danger`, `role="alert"`) mit Einleitungssatz und den
         `non_field_errors`; Klasse `errors` bleibt zusätzlich erhalten.
      2. Pflichtfeld-Hinweis, falls `form|has_required`.
      3. Versteckte Felder unverändert.
      4. Pro sichtbarem Feld: bei `field.use_fieldset` (Mehrfach-Checkboxen)
         `<fieldset>` + `<legend>` und Chip-Container, sonst `<label for>` +
         `{{ field|bs_widget }}`; einzelne Checkbox als `form-check`. Danach
         Hilfetext (`id="<auto_id>_helptext"`, `form-text`) und Fehler
         (`id="<auto_id>_error"`, `invalid-feedback d-block`).

      `core/_status_badge.html` -- `planned` → `text-bg-secondary`,
      `in-progress` → `text-bg-primary`, `done` → `text-bg-success`, jeweils mit
      Icon (`aria-hidden`) **und** Statustext.

- [ ] **Schritt 3: base.html**
      - `<head>`: Bootstrap-CSS und Icons-CSS mit SRI (SHA-384 aus den
        ausgelieferten Dateien berechnet) + `crossorigin="anonymous"`;
        Inline-SVG-Favicon (beseitigt den 404 auf `/favicon.ico` im Log).
      - Kleiner `<style>`-Block nur noch für das, was Bootstrap nicht mitbringt:
        Ressourcen-Typfarben `.badge-article/-video/-repo/-doc`, Chip-Optik für
        Checkbox-Gruppen (`label:has(input:checked)`), KPI-Icon-Kreis, Avatar.
        Die alten `.kpi-*`/`.bar*`/`.dashboard-table`/`.messages`-Regeln entfallen.
      - Skip-Link (`visually-hidden-focusable`) → `<main id="main-content">`.
      - Navbar `navbar-expand-lg` mit `data-bs-theme="dark"`, Toggler mit
        `aria-controls`/`aria-expanded`/`aria-label`, Links über `{% nav_link %}`,
        User-Dropdown mit POST-Logout als `<button class="dropdown-item">`.
      - Messages als `alert-dismissible` (`error` → `danger`), Footer.
      - `bootstrap.bundle.min.js` mit SRI am Ende von `<body>`.

- [ ] **Schritt 4: Business-Logik / Views** -- `SessionListView` erhält
      `get_queryset()` mit `super().get_queryset().prefetch_related("tags")`.
      Der bestehende `select_related("goal")` aus `OwnSessionMixin` bleibt
      erhalten, das Scoping ebenso.

- [ ] **Schritt 5: UI / Templates -- Seiten**

      | Template | Umsetzung |
      |---|---|
      | `home.html` | Anonym: Hero (`p-5 bg-body-tertiary rounded-3`) mit Login/Registrieren-CTA. Angemeldet: 4 Schnellzugriffs-Cards (Dashboard, Goals, Sessions, Profil) |
      | `login.html`, `register.html` | `row justify-content-center` → `col-md-7 col-lg-5` → Card mit Icon-Kopf; `_form.html`; `btn-primary w-100`; Wechsel-Link im Card-Footer. Login behält den Satz "Benutzername oder Passwort ist falsch." als `error_intro` |
      | `profile_detail.html` | Card: Initialen-Avatar, Name, Cohort, Focus Areas als `badge rounded-pill`; Platzhaltertexte unverändert |
      | `profile_form.html`, `goal_form.html`, `learningsession_form.html` | `col-lg-8` Card; `_form.html`; Footer-Buttons Speichern / Abbrechen |
      | `dashboard.html` | KPI-Row `row-cols-1 row-cols-md-3` mit Icon-Cards; 3 Tabellen-Cards (`table table-hover align-middle`, `caption`, `scope="col"`); Bootstrap-`progress` mit `{% widthratio … as pct %}` und ARIA-Werten; Status-Zeilen mit `_status_badge.html` |
      | `goal_list.html` | Kopf mit "Neues Lernziel"-Button; Filter als Inline-Form (`form-select`, `id="status"`); Card-Grid `row-cols-1 row-cols-md-2 row-cols-xl-3`; pro Card Status-Badge, gekürzte Beschreibung, Aktionen im Footer |
      | `goal_detail.html` | Kopf mit Titel, Badge, Aktionen; `col-lg-8`: Details-Card, Sessions-Tabelle, Ressourcen-Card mit Formular; `col-lg-4`: KI-Card mit beiden POST-Buttons und den Ergebnis-Sections (Klassen `ai-summary`/`ai-next-steps` bleiben) |
      | `_resource_list.html` | `list-group` mit `badge badge-{typ}`, externem Link (Icon + visuell versteckter Hinweis "öffnet in neuem Tab") und Entfernen-Button mit `aria-label` |
      | `learningsession_list.html` | Tabelle Datum / Lernziel / Dauer / Tags (Badges), responsive über `table-responsive` |
      | `learningsession_detail.html` | Card mit `dl.row`, Tags als Badges, Aktionen |
      | 3× `*_confirm_delete.html` | Card `border-danger` mit Warn-Icon, `btn-danger` + Abbrechen; Lösch-Formular bleibt POST |

- [ ] **Schritt 6: Tests** (`core/tests/test_ui.py`) -- siehe Abschnitt 4.

- [ ] **Schritt 7: Validierung** -- `python manage.py check`,
      `makemigrations --check --dry-run`, `ruff check .`, `python manage.py test`,
      anschließend `.\.workflow\hooks\validate_code.ps1`. Zusätzlich jede Seite
      einmal im laufenden Server aufrufen.

## 4. Validierung & Test-Strategie

**Regression:** Die 145 bestehenden Tests sind der primäre Nachweis, dass URLs,
Feldnamen, IDs und Texte unverändert sind. **Kein bestehender Test wird
angepasst.**

**Neue Tests** in `core/tests/test_ui.py`:

| Testklasse | Testfall | Prüft |
|---|---|---|
| `BootstrapEinbindungTests` | `test_bootstrap_css_und_js_mit_sri` | CSS, Icons und Bundle-JS jeweils mit `integrity="sha384-…"` und `crossorigin="anonymous"` |
| | `test_skip_link_und_main_landmark` | Skip-Link auf `#main-content`, `<main id="main-content">` vorhanden |
| `NavigationTests` | `test_aktiver_link_dashboard` | auf `/dashboard/` trägt nur der Dashboard-Link `aria-current="page"` |
| | `test_goal_detail_markiert_goals` | Goal-Detailseite markiert den Goals-Link aktiv |
| | `test_session_seiten_markieren_sessions` | Session-Liste markiert den Sessions-Link aktiv |
| | `test_logout_ist_post_formular_im_dropdown` | Dropdown enthält `<form … method="post">` auf `/accounts/logout/` mit CSRF-Token |
| | `test_anonym_sieht_login_und_registrieren` | kein Dropdown, dafür Login-/Registrieren-Links |
| `FormularDarstellungTests` | `test_felder_mit_bootstrap_klassen` | Goal-Formular: `form-control` am Titel, `form-select` am Status, IDs `id_title`/`id_status` unverändert |
| | `test_fehler_markiert_feld` | ungültiger POST: `is-invalid`, `aria-invalid="true"`, `aria-describedby` zeigt auf `id_<feld>_error`, Fehlerelement existiert |
| | `test_mehrfachauswahl_als_fieldset` | Session-Formular: Tags in `<fieldset>` mit `<legend>` |
| | `test_login_formular_gestylt` | Login: `form-control` an `id_username`/`id_password`, ohne `forms.py`-Änderung |
| `TemplateTagTests` | `test_bs_widget_klassen_je_widget_typ` | Filter direkt: TextInput → `form-control`, Select → `form-select`, Checkbox → `form-check-input` |
| | `test_bs_widget_behaelt_vorhandene_klasse_und_placeholder` | `placeholder` aus `ResourceForm` bleibt erhalten |
| | `test_has_required` | `True` für GoalForm, `False` für ein Formular ohne Pflichtfelder |
| `SeitenDarstellungTests` | `test_status_badge_mit_text` | Goal-Liste zeigt Badge `text-bg-success` **mit** Text "Erledigt" |
| | `test_dashboard_progressbar_aria` | Dashboard mit Daten: `role="progressbar"` mit `aria-valuenow` |
| | `test_session_liste_zeigt_tags_ohne_n_plus_1` | Tags als Badges; `assertNumQueries` bleibt bei 3 vs. 6 Sessions konstant |
| | `test_externer_link_kuendigt_neuen_tab_an` | Ressourcen-Link mit `target="_blank"` enthält den visuell versteckten Hinweis |

**Kommandos** (im aktiven `.venv`):

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

**Manuelle Sichtprüfung:** Server starten, als Testnutzer jede Seite aufrufen
(Startseite, Login, Registrierung, Profil + Bearbeiten, Dashboard, Goal-Liste,
-Detail, -Formular, -Löschen, Session-Liste, -Detail, -Formular, -Löschen,
Ressource-Löschen) und Status 200 sowie das Fehlen von Template-Fehlern prüfen.

**Abnahmekriterium:** `validate_code.ps1` endet mit Exit-Code 0, alle 145
Bestandstests unverändert grün, alle neuen UI-Tests grün.
