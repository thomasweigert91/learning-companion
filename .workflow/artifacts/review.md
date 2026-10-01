# Code Review: Export & Backup Center (CSV, Markdown-ZIP, JSON)

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17. **275 Tests** (244 Bestand + 31 neu), `ruff check .` ohne Befund, `makemigrations --check` sauber (keine Migration nötig), `validate_code.ps1` Exit-Code 0.

> **Isolation per Mutationstest belegt:** Werden die Filter `user=user` bzw. `goal__user=user` in `export_service.py` testweise durch `.all()` ersetzt, schlagen 10 der 31 neuen Tests fehl, darunter alle drei `test_keine_fremd*`-Tests. Danach wurde der Originalstand wiederhergestellt.

---

## 1. Abdeckung der Akzeptanzkriterien

### Seite & Navigation

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| `/export/` (`core:export_center`), LoginRequired, Redirect mit `next` | `ExportCenterView(LoginRequiredMixin, …)`; `test_anonym_wird_zum_login_umgeleitet` (alle vier Routen) | ja |
| Menüpunkt "Export" (`download`), aktiv auf Export-Routen, genau ein aktiver Link | `NAV_SECTIONS` um `("export", "export")` erweitert; `test_menuepunkt_export_ist_aktiv`, `test_menuepunkt_auf_anderen_seiten_inaktiv`; Bestandstest `test_genau_ein_nav_link_aktiv` weiter grün | ja |
| Je Option eine Card mit Beschreibung, Umfang, Download; eine `<h1>`, Icons `aria-hidden` | `export_center.html`; `test_seite_zeigt_umfang_und_drei_downloads`, `test_eine_h1_und_versteckte_icons` | ja |

### Export 1: CSV

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Route, nur GET | `ExportDownloadMixin` definiert nur `get`; `test_downloads_nur_per_get` (405) | ja |
| `StreamingHttpResponse`, Content-Type, Content-Disposition mit Datum | `test_streaming_response_mit_headern` | ja |
| Exakter Header `Goal,Date,Duration (min),Tags,Notes` | `test_bom_und_exakter_header` vergleicht die erste Rohzeile als String | ja |
| Eine Zeile je Session, chronologisch, ISO-Datum, Minuten, Tags `; `-getrennt, mehrzeilige Notiz korrekt gequotet | `test_eine_zeile_je_session_chronologisch`: Sessions bewusst in umgekehrter Reihenfolge angelegt; Notiz mit Zeilenumbruch, Komma und Anführungszeichen übersteht den Roundtrip über `csv.reader` | ja |
| UTF-8-BOM | `test_bom_und_exakter_header` | ja |
| Formel-Schutz `=`, `+`, `-`, `@`, Tab, CR | `_csv_safe`; `test_eine_zeile_je_session_chronologisch` (`'=SUMME…`), `test_formel_praefixe_werden_neutralisiert` (Titel `@…`, Notizen `+`, `-`, Tab) | ja |
| Ohne Sessions nur Header | `test_ohne_sessions_nur_header` | ja |
| Abfragezahl konstant | `iterator(chunk_size=500)` + `prefetch_related("tags")`; `test_abfragezahl_unabhaengig_von_sessionzahl` (2 vs. 7 Sessions) | ja |

### Export 2: Markdown-ZIP

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Route, nur GET, `FileResponse`, `application/zip`, Content-Disposition | `test_file_response_mit_headern` | ja |
| Gültiges ZIP, eine Datei `goals/<pk>-<slug>.md` je Goal; gleicher Titel -> zwei Dateien; leerer Slug -> `goal` | `test_gueltiges_zip_mit_einer_datei_je_goal` (inkl. Umlaut `Über` -> `uber`), `test_gleicher_titel_und_leerer_slug` | ja |
| Frontmatter mit allen Feldern; Titel mit `:`, `"`, `#` bleibt gültig | `test_frontmatter`, `test_titel_im_frontmatter_ist_gueltiger_string` (Titel `Django: "ORM" #1` per `json.loads` zurückgelesen) | ja |
| `# Titel`, Beschreibung, Ressourcen-Links, Sessions chronologisch; Hinweise bei leeren Abschnitten | `test_inhalt_mit_ressourcen_und_sessions` (eckige Klammern im Linktext escaped), `test_leeres_goal_zeigt_hinweise` | ja |
| Ohne Goals leeres, gültiges ZIP | `test_ohne_goals_leeres_zip` | ja |

### Export 3: JSON-Dump

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Route, nur GET, Content-Type, Content-Disposition | `test_response_mit_headern` | ja |
| UTF-8 ohne Escapes, eingerückt | `test_utf8_ohne_escapes_und_eingerueckt` (`Änne Ärger` im Rohtext) | ja |
| `format_version`, `exported_at`, `user`, `profile`, `goals` mit allen Kind-Daten | `test_konto_und_profil` (Schlüsselmenge von `user` exakt geprüft), `test_goals_mit_allen_kinddaten` | ja |
| `statistics` (Status auch mit 0, Mehrfach-Tags in jeder Kategorie, absteigend) | `test_statistiken` vergleicht den kompletten Block | ja |
| Keine sicherheitsrelevanten Felder | Allowlist statt `model_to_dict`; `test_keine_sicherheitsrelevanten_felder` (`password`, `pbkdf2`, `is_staff`, `is_superuser`, `last_login`) | ja |
| Abfragezahl konstant | `test_abfragezahl_unabhaengig_von_goalzahl` (2 vs. 5 Goals, jeweils mit Kind-Daten) | ja |

### Isolation & Tests

| Kriterium | Nachweis | Erfüllt |
|---|---|---|
| Alle Querysets gehen von `request.user` aus, keine Nutzer-Parameter in URLs | `sessions_for_export` (`goal__user=user`), `goals_for_export` (`user=user`), Kind-Daten nur per Prefetch der gescopten Goals; Routen ohne PK | ja |
| Fremddaten-Tests für jeden Export | Nutzer B hat in **jedem** Modell `FREMD`-markierte Texte und teilt die Tags mit A; `test_keine_fremden_sessions`, `test_keine_fremden_goals`, `test_keine_fremddaten` (zusätzlich Username und E-Mail von B) | ja |
| `core/tests/test_export.py`, Suite + `check` grün | 31 Tests; 275/275 grün | ja |

---

## 2. Sicherheit

- **Auth-Bypass:** Alle vier Views erben `LoginRequiredMixin`. Es gibt keinen Parameter, über den sich ein anderer Account adressieren ließe; die Service-Funktionen nehmen den Nutzer entgegen und filtern selbst.
- **SQL-Injection:** Ausschließlich ORM-Abfragen, keine Raw-SQL, keine Nutzereingaben in Abfragen.
- **CSV-Injection:** Neutralisiert (s. o.). Der JSON-Dump bleibt bewusst verlustfrei, wie im Ticket festgelegt.
- **Datenabfluss über Caches:** `add_never_cache_headers` setzt `no-store, private` auf allen Downloads (`test_downloads_werden_nicht_gecacht`).
- **Header-Injection:** Dateinamen werden serverseitig aus festen Bausteinen und dem Datum gebildet, ohne Nutzereingaben.
- **XSS:** Die Export-Seite gibt nur Zähler aus, Django escaped automatisch.
- **Ressourcen:** Das ZIP entsteht im Speicher. Das ist für die Datenmengen eines einzelnen Nutzers vertretbar und im Ticket als Rahmenbedingung festgehalten. Die potenziell längste Liste (Sessions) wird gestreamt.

## 3. Code-Qualität

- Die Logik liegt in `core/services/export_service.py`, rein lesend. Die Views sind dünn, und `ExportDownloadMixin` bündelt GET-only und No-Cache an einer Stelle.
- Kommentare und Benennung folgen dem Bestand (deutsche Kommentare, ae/oe/ue im Code).
- Keine toten Code-Pfade gefunden. `ruff check .` ist sauber, die neuen Dateien sind mit `ruff format` formatiert. Bestandsdateien wurden bewusst nicht umformatiert.

## 4. Hinweise (nicht blockierend)

1. Der Formel-Schutz setzt auch vor Notizen, die mit `- ` beginnen (Markdown-Listen), ein `'`. Das ist der dokumentierte Preis für OWASP-konformes Verhalten. Wer die Notizen unverändert braucht, nimmt den JSON-Export.
2. `exported_at` und die Zeitstempel im JSON stehen in UTC (`…Z`), die Markdown-Frontmatter in Ortszeit (`+02:00`). Beides ist eindeutiges ISO 8601. Bei Bedarf lässt sich das später vereinheitlichen.
3. Keine Sichtprüfung im Browser in diesem Durchlauf, damit die lokale Entwicklungsdatenbank nicht um einen Testnutzer erweitert wird. Das Rendering ist über die Template-Tests abgedeckt (Status 200, Links, `<h1>`, ARIA). Eine einmalige manuelle Prüfung von `/export/` vor dem Deployment wird empfohlen.
4. Unabhängig von diesem Feature: In der README-Projektstruktur fehlt bei `models.py` noch `Flashcard` (aus Feature 9).
