# Implementierungs-Plan: Export & Backup Center

## 1. Betroffene Dateien

- Neu: `core/services/export_service.py` (reine Lese-Logik: CSV-Zeilen, Markdown, ZIP, JSON-Dump, Statistiken)
- Ändern: `core/views.py` (vier Views: Export-Seite, CSV, ZIP, JSON)
- Ändern: `core/urls.py` (vier Routen unter `export/`)
- Ändern: `core/templatetags/ui.py` (Navigationsbereich `export`)
- Ändern: `core/templates/base.html` (Menüpunkt "Export")
- Neu: `core/templates/core/export_center.html` (Seite mit drei Cards)
- Neu: `core/tests/test_export.py`
- Ändern: `README.md` (Funktionsabschnitt "Export & Backup")

## 2. Datenmodelle & Migrationen

Keine. Es werden ausschließlich bestehende Modelle gelesen (`Goal`,
`LearningSession`, `Tag`, `Resource`, `AIFeedback`, `Flashcard`, `Profile`).
Keine Migration, keine neue Abhängigkeit (nur `csv`, `zipfile`, `json`, `io`).

Scoping-Einstieg ist immer `request.user`:

- Goals: `Goal.objects.filter(user=user)`
- Sitzungen: `LearningSession.objects.filter(goal__user=user)`
- Kind-Daten der Goals (Ressourcen, KI-Einträge, Lernkarten, Sitzungen) nur per
  `prefetch_related` über die bereits gescopten Goals -- strukturell kein
  Fremdzugriff möglich.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Setup -- Service-Modul** `core/services/export_service.py`

      *CSV:*
      - `CSV_HEADER = ["Goal", "Date", "Duration (min)", "Tags", "Notes"]`
      - `_csv_safe(wert)`: Text mit führendem `=`, `+`, `-`, `@`, `\t`, `\r`
        erhält ein `'` (OWASP CSV Injection).
      - `sessions_for_export(user)`: `filter(goal__user=user)
        .select_related("goal").prefetch_related("tags").order_by("date", "pk")`
        (Tags kommen über `Tag.Meta.ordering` bereits alphabetisch).
      - `iter_sessions_csv(user)`: Generator; schreibt über einen
        Pseudo-Buffer (`write()` gibt die Zeile zurück) mit `csv.writer` je
        Zeile einen String; erste Ausgabe ist BOM + Header. Iteration über
        `.iterator(chunk_size=500)` -- Prefetch bleibt seit Django 4.1 auch
        mit `iterator()` wirksam, die Abfragezahl bleibt konstant.

      *Markdown/ZIP:*
      - `goals_for_export(user)`: `Goal.objects.filter(user=user)
        .order_by("pk").prefetch_related(Prefetch("sessions", date/pk
        aufsteigend, mit Tags), "resources")`; der JSON-Dump ergänzt
        `ai_feedbacks` und `flashcards`.
      - `goal_filename(goal)`: `goals/<pk>-<slugify(title) or "goal">.md`.
      - `_yaml_str(wert)`: `json.dumps(wert, ensure_ascii=False)` -- ein
        JSON-String ist ein gültiger YAML-Double-Quoted-Scalar; damit sind
        `:`, `"`, `#` und Zeilenumbrüche sicher.
      - `goal_markdown(goal)`: Frontmatter (`id`, `title`, `status`,
        `created`, `updated`, `sessions`, `total_minutes`), `# Titel`,
        Beschreibung, `## Ressourcen`, `## Lernsitzungen` (je Sitzung
        `### JJJJ-MM-TT -- N Min.`, Tags, Notizen). `[`/`]` in Link-Texten
        werden escaped. Leere Abschnitte: `_Keine Ressourcen._` bzw.
        `_Keine Lernsitzungen._`
      - `build_goals_zip(user) -> io.BytesIO`: `ZipFile(..., "w",
        ZIP_DEFLATED)`, je Goal `writestr`, Puffer auf 0 zurückspulen.

      *JSON:*
      - `FORMAT_VERSION = 1`
      - `build_user_dump(user) -> dict`: `format_version`, `exported_at`,
        `user` (nur `username`, `email`, `date_joined`), `profile`
        (`name`, `cohort`, `focus_areas`, `created_at`, `updated_at`; `None`
        falls kein Profil), `goals` (alle Felder + verschachtelt `sessions`,
        `resources`, `ai_feedbacks`, `flashcards`), `statistics`.
        Feldauswahl explizit (Allowlist) -- kein `model_to_dict`, damit nie
        versehentlich `password`, `is_staff` usw. hineinrutschen.
      - `_statistics(goals)`: aus den bereits geladenen Daten, ohne weitere
        Abfragen: `goals_total`, `sessions_total`, `minutes_total`,
        `goals_by_status` (alle `Goal.Status`-Werte, auch 0),
        `minutes_by_tag` (Session mit mehreren Tags zählt -- wie im
        Dashboard -- in jede Kategorie; sortiert `-minutes`, `tag`).
      - `export_filename(art, endung)`:
        `learning-companion-<art>-<timezone.localdate()>.<endung>`.

- [ ] **Schritt 2: Business-Logik / Views** (`core/views.py`, Abschnitt "Export")
      - `ExportCenterView(LoginRequiredMixin, TemplateView)`: Kontext
        `sessions_anzahl`, `goals_anzahl` (gescopte `count()`).
      - `ExportSessionsCSVView(LoginRequiredMixin, View)`, nur `get`:
        `StreamingHttpResponse(iter_sessions_csv(user),
        content_type="text/csv; charset=utf-8")` + `Content-Disposition`.
      - `ExportGoalsZipView(LoginRequiredMixin, View)`, nur `get`:
        `FileResponse(build_goals_zip(user), as_attachment=True,
        filename=..., content_type="application/zip")`.
      - `ExportJSONView(LoginRequiredMixin, View)`, nur `get`:
        `HttpResponse(json.dumps(dump, cls=DjangoJSONEncoder,
        ensure_ascii=False, indent=2), content_type="application/json;
        charset=utf-8")` + `Content-Disposition: attachment`.
      - Gemeinsamer `ExportDownloadMixin`: definiert nur `get` (POST & Co.
        -> 405) und setzt per `add_never_cache_headers` `Cache-Control:
        no-store` -- persönliche Daten sollen in keinem Browser- oder
        Proxy-Cache landen. Die Unterklassen liefern nur `build_response(user)`.
      - Routen (`core/urls.py`): `export/` -> `export_center`,
        `export/sessions.csv` -> `export_sessions_csv`,
        `export/goals.zip` -> `export_goals_zip`,
        `export/data.json` -> `export_json`. Keine PK-Parameter.

- [ ] **Schritt 3: UI / Templates**
      - `core/templatetags/ui.py`: `("export", "export")` in `NAV_SECTIONS`.
      - `base.html`: `{% nav_link "core:export_center" "Export" "download" "export" %}`
        nach "Sessions".
      - `export_center.html`: Kopf mit `<h1>`, drei Cards (CSV / Markdown-ZIP /
        JSON) mit Icon, Text, Umfang und `<a class="btn ..." href="..."
        download>`; Hinweis zur DSGVO und dass ausschließlich eigene Daten
        exportiert werden. Alle `<i class="bi ...">` mit `aria-hidden="true"`.
      - README: Abschnitt "Export & Backup" unter "Funktionen".

- [ ] **Schritt 4: Tests** (`core/tests/test_export.py`)

## 4. Validierung & Test-Strategie

Testdaten: Nutzer A mit zwei Goals (eines mit Sonderzeichen-Titel
`Django: "ORM" #1`, eines ohne Sitzungen), Sitzungen mit mehreren Tags,
mehrzeiligen Notizen und einer Notiz `=SUMME(A1)`, Ressource, KI-Eintrag,
Lernkarte. Nutzer B mit eindeutig markierten Daten (`FREMD-...`) in allen
Modellen und denselben Tags.

- **Zugriff:** alle vier Routen anonym -> 302 auf Login mit `next`;
  POST auf die drei Downloads -> 405; Downloads tragen `no-store`.
- **CSV:** `StreamingHttpResponse`, Content-Type, Content-Disposition mit
  Datum; BOM vorhanden; erste Zeile exakt `Goal,Date,Duration (min),Tags,Notes`;
  Zeilenzahl = Sitzungen von A; Reihenfolge aufsteigend; Tags `Django; Python`;
  mehrzeilige Notiz per `csv.reader` unverändert; Formel mit `'` neutralisiert;
  leerer Nutzer -> nur Header; Abfragezahl bei 1 vs. 5 Sitzungen gleich.
- **ZIP:** `FileResponse`, Content-Type, Content-Disposition; `zipfile.is_zipfile`;
  Dateinamen = `goals/<pk>-<slug>.md` je Goal von A; gleicher Titel -> zwei
  Dateien; Frontmatter-Werte per Zeilenvergleich (Titel gequotet), Ressourcen-
  Link, Sitzungen, Hinweistext bei leerem Goal; leerer Nutzer -> leeres ZIP.
- **JSON:** Content-Type, Content-Disposition, `json.loads`; Struktur und
  verschachtelte Daten; Umlaute unescaped; `password`/`is_staff`/`is_superuser`
  nirgends im Text; Statistiken korrekt (Status mit 0, Mehrfach-Tags);
  Abfragezahl bei 1 vs. 4 Goals gleich.
- **Isolation:** für jeden Export: kein `FREMD`-Marker im entpackten Inhalt.
- **Navigation/UI:** Seite rendert mit Zählern und drei Download-Links;
  "Export" aktiv auf `/export/`, genau ein aktiver Nav-Link, eine `<h1>`,
  Icons `aria-hidden`.

Kommandos:

```
python manage.py check
python manage.py test
ruff check .
.\.workflow\hooks\validate_code.ps1
```
