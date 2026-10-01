# Code Review: UI- und Styling-Upgrade auf Bootstrap 5

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Bootstrap 5.3.8, Bootstrap Icons 1.13.1.
**175 Tests** (145 Bestand + 30 neu), `ruff check .` ohne Befund, `validate_code.ps1` Exit-Code 0.

> **Geprüft wurde nicht nur das HTML, sondern die gerenderte Oberfläche.** Tests sehen nicht, ob CSS im Browser tatsächlich ankommt — ein falscher SRI-Hash etwa würde das Stylesheet stillschweigend verwerfen. Deshalb wurden alle Seitentypen mit Playwright in Desktop- (1280 px) und Handybreite (390 px) aufgerufen, gemessen und als Screenshot begutachtet. Dabei wurde ein Darstellungsfehler gefunden und behoben (Abschnitt 4).

---

## 1. Vollständigkeit

### Abdeckung der Seiten

| Bereich | Templates | Umgesetzt |
|---|---|---|
| Navigation | `base.html`, `_nav_link.html` | Navbar mit Collapse, aktiver Bereich, User-Dropdown, Skip-Link, Alerts, Footer |
| Startseite | `home.html`, `_home_card.html` | Hero (anonym), Schnellzugriffs-Cards (angemeldet) |
| Auth | `login.html`, `register.html` | zentrierte Cards, `form-control`, volle Button-Breite |
| Profil | `profile_detail.html`, `profile_form.html` | Avatar-Card mit Focus-Area-Badges; Formular-Card mit Chips |
| Dashboard | `dashboard.html` | 3 KPI-Karten, 3 Tabellen-Cards mit `progress`-Balken |
| Goals | `goal_list.html`, `goal_detail.html`, `goal_form.html`, `goal_confirm_delete.html`, `_status_badge.html` | Card-Grid mit Status-Badges und Aktionen; Detail mit Sessions-Tabelle, Ressourcen, KI-Card |
| Sessions | `learningsession_list.html`, `…_detail.html`, `…_form.html`, `…_confirm_delete.html` | Tabelle mit Tag-Badges; Detail-Card; Formular mit Chips |
| Resources | `_resource_list.html`, `resource_confirm_delete.html` | List-Group mit Typ-Badges; Lösch-Card |
| Formulare (alle) | `_form.html` + `core/templatetags/ui.py` | ein Partial für alle sechs Formulare inkl. Djangos `AuthenticationForm` |

`git diff --name-only -- core/templates/` → **alle 17** Bestands-Templates geändert. Kein `{{ form.as_p }}` und keine Regel des alten Hand-CSS (`.kpi-card`, `.bar-track`, `.dashboard-table`) mehr vorhanden.

### Akzeptanzkriterien

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | Bootstrap 5.3.8 + Icons 1.13.1 per CDN | `base.html`; im Browser: `bootstrap.min.css` mit 1297 Regeln, Icons-CSS mit 2080 Regeln, `window.bootstrap` meldet 5.3.8 | ja |
| 2 | SRI + `crossorigin` an allen drei Ressourcen | Hashes aus den ausgelieferten Dateien berechnet (`openssl dgst -sha384`); `test_bootstrap_css_und_js_mit_sri`; **Browser hat alle drei akzeptiert**, 0 Konsolenfehler | ja |
| 3 | Script am Ende von `<body>` | `test_script_steht_am_ende_des_body` | ja |
| 4 | Responsive Navbar mit Toggler | Handybreite: Toggler klappt auf, `aria-expanded` wechselt auf `true` | ja |
| 5 | Aktiver Link mit `.active` **und** `aria-current` | `NavigationTests` (6 Fälle): Dashboard, Goal-Detail, Resource-Route, Session-Seiten, genau ein aktiver Link | ja |
| 6 | User-Dropdown, Logout als POST | `test_logout_ist_post_formular_im_dropdown` (Form + CSRF-Token im Dropdown); im Browser aufgeklappt | ja |
| 7 | Anonym: Login/Registrieren statt Dropdown | `test_anonym_sieht_login_und_registrieren` | ja |
| 8 | `test_navbar_enthaelt_dashboard_link` grün | unverändert grün | ja |
| 9 | Container, Alerts (`error` → `danger`) | `base.html`; Fehlermeldungen der KI-Views erscheinen weiterhin (`test_ai_views`) | ja |
| 10–17 | Seiten-Layouts laut Ticket | Abschnitt "Abdeckung"; Screenshots aller Seitentypen begutachtet | ja |
| 18 | Ein Formular-Partial, `forms.py` unangetastet | `git diff core/forms.py` leer; Login gestylt (`test_login_formular_gestylt`) | ja |
| 19 | `is-invalid`, `aria-invalid`, `aria-describedby` | `test_fehler_markiert_feld`; siehe Abschnitt 3 zur Herkunft der ARIA-Attribute | ja |
| 20 | Pflichtfelder markiert, Hinweis am Formular | `test_pflichtfeld_hinweis`; Login bewusst ohne (`test_login_ohne_pflichtfeld_hinweis`) | ja |
| 21–26 | Barrierefreiheit | siehe Abschnitt 2 | ja |
| 27 | 145 Bestandstests unverändert grün | `git diff --name-only -- core/tests/` → **leer**; 145/145 grün | ja |
| 28 | URLs, Feldnamen, IDs, `badge-{typ}` erhalten | `id="status"`, `id_<feld>`, `badge-article/-video/-repo/-doc`; `test_resource_badge_class_matches_type` grün | ja |
| 29 | KI-Begriffe nur mit Ergebnis | `test_ai_views` (prüft Abwesenheit) grün; die Wörter stehen ausschließlich in den `{% if %}`-Blöcken | ja |
| 30 | Neue Tests für die Kernpunkte | `core/tests/test_ui.py`, 30 Tests | ja |
| — | Sessions ohne N+1 | `prefetch_related("tags")`; `test_session_liste_zeigt_tags_ohne_n_plus_1` (Query-Zahl bei 3 und 6 Sessions identisch) | ja |

---

## 2. Barrierefreiheit

### Im Browser verifiziert

| Prüfung | Ergebnis |
|---|---|
| Skip-Link ist erstes Tab-Ziel | Tab → Fokus auf "Zum Inhalt springen", Element sichtbar |
| Skip-Link verschiebt den **Fokus**, nicht nur die Scrollposition | Enter → `document.activeElement` ist `MAIN#main-content` (dank `tabindex="-1"`) |
| Navbar-Toggler und Dropdown melden ihren Zustand | `aria-expanded` wechselt beim Öffnen auf `true` |
| Kein horizontales Scrollen in Handybreite | `scrollWidth ≤ innerWidth` auf Profil, Dashboard, Goal-Liste, Goal-Detail, Sessions, Lösch-Bestätigung |
| Clickjacking-Schutz intakt | Einbetten per `<iframe>` wird von `X-Frame-Options: DENY` blockiert |

### Statisch und per Test geprüft

| Kriterium | Nachweis |
|---|---|
| Dekorative Icons `aria-hidden="true"` | `grep` über alle Templates: kein `<i class="bi …">` ohne; `test_dekorative_icons_sind_versteckt` auf vier Seiten |
| Icon-only-Buttons mit zugänglichem Namen | Bearbeiten/Löschen in der Goal-Liste und Entfernen bei Ressourcen tragen `aria-label` mit dem Objektnamen ("Ressource Doku entfernen"), nicht nur "Entfernen"; `test_icon_buttons_haben_zugaenglichen_namen` |
| "Details"-Links unterscheidbar | visuell versteckter Zusatz "zu <Titel>" — Screenreader-Linklisten zeigen nicht zehnmal "Details" |
| Tabellen | `<caption>` + `<th scope="col">` in allen Tabellen; `test_tabellen_mit_caption_und_scope` |
| Progress-Balken | `role="progressbar"`, sprechendes `aria-label` ("Python: 200 Minuten"), `aria-valuenow/-min/-max`; `test_dashboard_progressbar_aria` |
| Neuer Tab angekündigt | visuell versteckt "(oeffnet in neuem Tab)"; alle `_blank`-Links mit `rel="noopener noreferrer"` |
| Genau eine `<h1>` | `test_genau_eine_h1_je_seite` über 11 Seiten. `home.html` enthält zwei `<h1>`, die aber in exklusiven `{% if %}`/`{% else %}`-Zweigen stehen |
| Status nie nur über Farbe | jedes Badge enthält Icon **und** Text; `test_status_badge_mit_text` |
| Checkbox-Gruppen | `<fieldset>` + `<legend>` statt eines einzelnen `<label>`; `test_mehrfachauswahl_als_fieldset` |
| Landmarks | `<header>`, `<nav aria-label="Hauptnavigation">`, `<main>`, `<footer>`; Breadcrumbs als eigene `<nav>` mit `aria-current="page"` |
| Reduzierte Bewegung | Hover-Anhebung der Cards unter `prefers-reduced-motion: reduce` abgeschaltet |
| Kontrast | Bootstrap-`text-bg-*` erfüllt AA; die vier Ressourcen-Badge-Farben erreichen mit weißer Schrift je ≥ 4,5:1 |

**Eine Anmerkung ohne Nachbesserungsbedarf:** Der gelbe Wochen-Balken (`bg-warning`) erreicht gegen seine graue Spur nicht das 3:1-Kontrastziel für Grafiken (WCAG 1.4.11). Er ist aber rein ergänzend — derselbe Wert steht als Zahl in der Nachbarspalte und als `aria-label` am Balken. Es geht keine Information verloren.

---

## 3. Befund im Zuge der Umsetzung: ARIA kommt von Django selbst

Der Plan sah vor, dass der Filter `bs_widget` `aria-describedby` selbst zusammensetzt — mit der Begründung, Django verknüpfe sonst nur den Hilfetext. Eine **Mutationsprobe** hat diese Annahme widerlegt: Nach Entfernen der eigenen Fehler-Verknüpfung blieb `test_fehler_markiert_feld` grün.

Ursache (`django/forms/boundfield.py`): Seit **Django 5.2** erzeugt `BoundField.aria_describedby` selbst `aria-invalid` und `aria-describedby` nach der Konvention `<id>_helptext` / `<id>_error`. Die Annahme galt nur für 5.0/5.1.

Konsequenz:

- Der eigene ARIA-Code wurde **entfernt**; `bs_widget` vergibt nur noch die CSS-Klasse. Das Partial stellt sicher, dass Hilfe- und Fehlertext genau die IDs tragen, auf die Django verweist.
- Weil das Verhalten erst ab 5.2 existiert, wurde der Pin in `requirements.txt` von `Django>=5.0` auf **`Django>=5.2`** angehoben. Installiert ist bereits 5.2.17 (LTS), das Docker-Image zieht ebenfalls 5.2.x — es ändert sich nichts an der laufenden Umgebung, nur die Untergrenze ist jetzt ehrlich.
- Gegenprobe an der Stelle, die tatsächlich von uns abhängt: Die Fehler-ID im Partial testweise umbenannt → `test_fehler_markiert_feld` **rot**. Der Test prüft also den Vertrag zwischen Partial und Django.

---

## 4. Befund der Sichtprüfung: Scrollleiste in Tabellen

**Gefunden:** In der Sessions-Tabelle erschien innerhalb der Card eine vertikale Scrollleiste.

**Ursache (im Browser gemessen):** `scrollHeight` 247 gegenüber `clientHeight` 246 — überlaufendes Element war die visuell versteckte `<caption>`. Bootstrap 5.3 nimmt Captions bewusst von `position: absolute` aus (`.visually-hidden:not(caption)`), weil absolut positionierte Captions das Tabellenlayout stören. Die Caption bleibt also 1 px hoch im Fluss. Da `.table-responsive` `overflow-x: auto` setzt, wird nach CSS-Spezifikation auch die y-Achse scrollbar.

**Behoben:** `.table-responsive { overflow-y: hidden; }` in `base.html`, mit Begründung im Kommentar. Der Wrapper soll ohnehin nur horizontal scrollen. Nachgemessen: `overflowY: hidden`, keine Scrollleiste, Caption-Text weiterhin im Accessibility-Baum.

Ein reiner HTML-Test hätte diesen Fehler nicht finden können — er existiert erst im Zusammenspiel von Bootstrap-CSS und Browser-Layout.

---

## 5. Sicherheit

- **SRI:** Alle drei CDN-Ressourcen mit SHA-384, berechnet aus den tatsächlich ausgelieferten Dateien — nicht aus Dokumentation oder Gedächtnis übernommen. Ein manipuliertes CDN-Asset würde der Browser verwerfen.
- **XSS:** Die einzige `|safe`-Stelle ist `{{ field.help_text|safe }}` in `_form.html`. Hilfetexte stammen aus Modell- und Formulardefinitionen (inkl. Djangos HTML-Liste der Passwortregeln), nie aus Nutzereingaben — identisch mit Djangos eigenem Standard-Template. Beschreibungen und Notizen werden neu per `|linebreaksbr` ausgegeben; der Filter escaped vor dem Umbruch.
- **CSRF:** Alle POST-Formulare (Logout im Dropdown, KI-Aktionen, Ressource entfernen, Lösch-Bestätigungen) tragen weiterhin `{% csrf_token %}`. Löschen bleibt ausschließlich POST.
- **Tabnabbing:** alle `target="_blank"`-Links mit `rel="noopener noreferrer"`.
- **Clickjacking:** `X-Frame-Options: DENY` unverändert wirksam (im Browser bestätigt).

---

## 6. Abweichungen gegenüber Ticket und Plan

| Abweichung | Bewertung |
|---|---|
| Django-Pin `>=5.2` statt `>=5.0` | Siehe Abschnitt 3. Macht eine tatsächliche Abhängigkeit sichtbar; die laufende Umgebung bleibt unverändert. |
| Checkbox-Gruppen werden im Partial selbst gerendert (Bootstrap-`btn-check`-Chips) statt über `bs_widget` | Notwendig: Djangos Gruppen-Template schreibt die übergebene `class` auch auf den äußeren Container-`<div>` — `form-check-input` hätte ihn als 1em-Checkbox gerendert. Namen, Werte und IDs (`id_tags_0` …) entsprechen exakt dem Django-Widget; `test_chip_auswahl_laesst_sich_absenden` und `test_gesetzter_tag_ist_vorausgewaehlt` belegen, dass das Formular die Auswahl unverändert annimmt. |
| `.table-responsive { overflow-y: hidden; }` | Fix aus der Sichtprüfung, Abschnitt 4. |
| Zusätzliches Partial `_home_card.html` | im Plan nachgetragen. |
| "Abbrechen" in Goal- und Session-Formularen führt beim **Bearbeiten** zur Detailseite statt zur Liste | Bewusste UX-Verbesserung: man landet dort, woher man kam. Beim Anlegen bleibt das Ziel die Liste. Reine Link-Ziele, kein View-Verhalten; streng gelesen eine kleine Abweichung von "Verhalten unverändert" und deshalb hier festgehalten. |
| Breadcrumbs auf Goal- und Session-Detail, "Erfassen"-Button in der Sessions-Card des Goals | additive Navigationshilfen auf bestehende URLs |
| Ein zunächst gesetztes `novalidate` an Login/Registrierung wurde wieder entfernt | hätte die native Browser-Validierung abgeschaltet und damit Verhalten geändert |

---

## 7. Verifikation

```powershell
ruff check .                                        # All checks passed!
python manage.py check                              # 0 Issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test                               # Ran 175 tests — OK
.\.workflow\hooks\validate_code.ps1                 # Exit-Code 0
git diff --name-only -- core/tests/                 # leer: kein Bestandstest angepasst
```

**Mutationsproben** (jeweils danach zurückgesetzt):

| Mutation | Ergebnis |
|---|---|
| `prefetch_related("tags")` entfernt | `test_session_liste_zeigt_tags_ohne_n_plus_1` rot |
| Eigene Fehler-Verknüpfung im Filter entfernt | **grün** → führte zum Befund in Abschnitt 3 |
| Fehler-ID im Partial umbenannt | `test_fehler_markiert_feld` rot |

**Sichtprüfung:** Login (leer und mit Fehler), Dashboard, Goal-Liste, Goal-Detail mit KI-Ergebnis, Sessions-Liste, Session-Formular mit Chips, Profil mit aufgeklapptem Mobil-Menü und Dropdown, Lösch-Bestätigung mobil. Dazu ein temporärer Prüfnutzer mit Beispieldaten, der anschließend samt Daten wieder gelöscht wurde; die Dev-Datenbank ist im Ausgangszustand.

---

## 8. Fazit

Alle Seiten sind auf ein einheitliches, responsives Bootstrap-5-Design umgestellt, ohne dass ein einziger Bestandstest angepasst werden musste. Die Barrierefreiheit wurde nicht nur am Markup, sondern im Browser geprüft (Fokusführung, Zustandsattribute, Überlauf in Handybreite). Zwei echte Befunde — eine falsche Annahme über Djangos ARIA-Verhalten und ein Layoutfehler durch versteckte Tabellen-Captions — wurden gefunden, ursächlich erklärt und behoben.

**Freigabe erteilt: APPROVED.**
