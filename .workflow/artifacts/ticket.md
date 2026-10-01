# Ticket: Export & Backup Center (CSV, Markdown-ZIP, JSON)

## 1. Problem / Ziel

Alle Lerndaten liegen bisher ausschliesslich in der Anwendung. Wer seine
Sitzungen in einer Tabellenkalkulation auswerten, seine Lernziele als Notizen in
ein Wiki oder Obsidian uebernehmen oder schlicht ein Backup ziehen will, hat
keinen Weg, die Daten herauszubekommen. Zusaetzlich verlangt Art. 20 DSGVO
(Recht auf Datenuebertragbarkeit), dass Nutzer ihre Daten in einem strukturierten,
gaengigen und maschinenlesbaren Format erhalten koennen.

Dieses Ticket ergaenzt ein **Export Center** unter `/export/` mit drei
Download-Optionen:

1. **CSV** aller Lernsitzungen -- fuer Excel, LibreOffice, Pandas.
2. **ZIP mit einer Markdown-Datei je Goal** -- lesbar, versionierbar, mit
   Metadaten-Frontmatter, Ressourcen und Sitzungshistorie.
3. **JSON-Dump** aller eigenen Daten -- vollstaendig und verlustfrei, zur
   Datenportabilitaet.

Wie ueberall in der Anwendung gilt: Ein Export enthaelt ausschliesslich Daten des
angemeldeten Nutzers.

## 2. Akzeptanzkriterien

### Seite & Navigation

- [ ] Neue Seite `/export/` (URL-Name `core:export_center`), nur fuer angemeldete
      Nutzer; anonym -> Redirect auf den Login mit `next`.
- [ ] Neuer Menuepunkt "Export" (Icon `download`) in der Hauptnavigation, der auf
      allen Export-Routen als aktiv markiert ist; weiterhin genau ein aktiver
      Nav-Link je Seite.
- [ ] Die Seite zeigt je Option eine Card mit Beschreibung, Umfang (Anzahl
      Sitzungen bzw. Goals) und einem Download-Button; genau eine `<h1>`,
      dekorative Icons mit `aria-hidden="true"`.

### Export 1: Lernsitzungen als CSV

- [ ] Route `/export/sessions.csv` (`core:export_sessions_csv`), nur GET,
      LoginRequired.
- [ ] Antwort ist eine `StreamingHttpResponse` mit
      `Content-Type: text/csv; charset=utf-8` und
      `Content-Disposition: attachment; filename="learning-companion-sessions-<JJJJ-MM-TT>.csv"`.
- [ ] Erste Zeile ist exakt der Header `Goal,Date,Duration (min),Tags,Notes`.
- [ ] Je `LearningSession` des Nutzers genau eine Zeile, chronologisch
      aufsteigend (`date`, dann `pk`); Datum im ISO-Format `JJJJ-MM-TT`,
      Dauer als ganze Minuten, Tags alphabetisch mit `; ` getrennt, Notizen
      unveraendert inkl. Zeilenumbruechen (korrektes CSV-Quoting).
- [ ] Die Datei beginnt mit einem UTF-8-BOM, damit Excel Umlaute korrekt
      anzeigt; ein Parser mit `utf-8-sig` liest Header und Daten unveraendert.
- [ ] Schutz gegen CSV-/Formel-Injection: Textzellen, die mit `=`, `+`, `-`,
      `@`, Tab oder Wagenruecklauf beginnen, erhalten ein fuehrendes `'`.
- [ ] Ohne Sitzungen wird eine gueltige CSV mit nur dem Header geliefert.
- [ ] Die Anzahl der DB-Abfragen ist unabhaengig von der Zahl der Sitzungen
      (kein N+1 fuer Goal oder Tags).

### Export 2: Goals als Markdown-ZIP

- [ ] Route `/export/goals.zip` (`core:export_goals_zip`), nur GET,
      LoginRequired.
- [ ] Antwort ist eine `FileResponse` mit `Content-Type: application/zip` und
      `Content-Disposition: attachment; filename="learning-companion-goals-<JJJJ-MM-TT>.zip"`.
- [ ] Das Archiv ist ein gueltiges ZIP und enthaelt genau eine Datei je eigenem
      Goal: `goals/<pk>-<slug>.md` (Slug aus dem Titel; leerer Slug -> `goal`).
      Zwei Goals mit gleichem Titel erzeugen zwei verschiedene Dateien.
- [ ] Jede Datei beginnt mit YAML-Frontmatter (`---` ... `---`) mit `id`,
      `title`, `status`, `created`, `updated`, `sessions` (Anzahl),
      `total_minutes`; Textwerte sind gequotet, sodass Doppelpunkte, Anfuehrungs-
      zeichen und `#` im Titel die Frontmatter nicht brechen.
- [ ] Danach folgen `# <Titel>`, die Beschreibung, ein Abschnitt
      `## Ressourcen` (je Ressource `- [Titel](URL) -- Typ`) und ein Abschnitt
      `## Lernsitzungen` (je Sitzung chronologisch: Datum, Dauer, Tags, Notizen).
      Leere Abschnitte zeigen einen kurzen Hinweis statt zu fehlen.
- [ ] Ohne Goals wird ein gueltiges, leeres ZIP geliefert.

### Export 3: JSON-Dump (DSGVO-Datenportabilitaet)

- [ ] Route `/export/data.json` (`core:export_json`), nur GET, LoginRequired.
- [ ] Antwort mit `Content-Type: application/json` und
      `Content-Disposition: attachment; filename="learning-companion-data-<JJJJ-MM-TT>.json"`;
      gueltiges, UTF-8-kodiertes JSON (Umlaute nicht escaped), eingerueckt.
- [ ] Inhalt: `format_version`, `exported_at` (ISO 8601), `user`
      (`username`, `email`, `date_joined`), `profile` (`name`, `cohort`,
      `focus_areas`, Zeitstempel) und `goals` -- je Goal alle Felder sowie
      verschachtelt `sessions` (inkl. Tags), `resources`, `ai_feedbacks` und
      `flashcards`.
- [ ] Ein Block `statistics` enthaelt die Kennzahlen des Dashboards:
      `goals_total`, `sessions_total`, `minutes_total`, `goals_by_status`
      (jeder Status, auch mit 0) und `minutes_by_tag` (absteigend nach Minuten).
- [ ] Sicherheitsrelevante Felder sind **nicht** enthalten: kein Passwort-Hash,
      keine Flags wie `is_staff`/`is_superuser`, keine Session- oder API-Schluessel.
- [ ] Die Anzahl der DB-Abfragen ist unabhaengig von der Zahl der Goals.

### Isolation

- [ ] Alle Querysets der Exporte filtern auf `request.user` (`user=` bzw.
      `goal__user=`); es gibt keinen URL-Parameter, ueber den ein anderer Nutzer
      adressiert werden koennte.
- [ ] Tests mit zwei Nutzern belegen fuer **jeden** der drei Exporte, dass kein
      Titel, keine Notiz, keine Ressource, keine Lernkarte und kein KI-Eintrag des
      anderen Nutzers enthalten ist.

### Tests

- [ ] Neue Testdatei `core/tests/test_export.py`: Login-Pflicht aller vier
      Routen, 405 fuer POST auf die Downloads, Response-Typen
      (`StreamingHttpResponse`/`FileResponse`), Header (Content-Type,
      Content-Disposition), exakter CSV-Header, CSV-Inhalt inkl. Quoting und
      Formel-Schutz, ZIP-Inhalt und Frontmatter, JSON-Struktur und Statistiken, ausgeschlossene
      Felder, Abfrage-Anzahl, Navigation.
- [ ] Die komplette Testsuite (`python manage.py test`) und `python manage.py check`
      laufen gruen.

## 3. Technische Rahmenbedingungen & Out-of-Scope

- Nur Python-Standardbibliothek (`csv`, `zipfile`, `json`, `io`); keine neue
  Abhaengigkeit, keine Migration.
- Die Export-Logik liegt datenbankseitig nur lesend in einem eigenen Modul
  `core/services/export_service.py`; die Views sind duenn.
- Downloads per GET sind vertretbar: sie sind rein lesend und haben keine
  Seiteneffekte. Sie sind durch Login und `request.user`-Scoping geschuetzt.
- Der Formel-Schutz gilt bewusst nur fuer die CSV (Zielgruppe
  Tabellenkalkulation). Der JSON-Dump bleibt verlustfrei; dort ist er
  unnoetig, und Markdown wird nicht als Formel interpretiert.
- **Out-of-Scope:** Import/Wiederherstellung aus einem Backup, asynchrone
  Erzeugung per Task-Queue oder E-Mail-Versand, zeitgesteuerte Backups,
  Exporte fuer Administratoren bzw. anderer Nutzer, Statistiken als eigene
  Datei (sie stehen im JSON-Block `statistics`, die Rohdaten in CSV und JSON),
  Wochen-Statistik, PDF-Export, Konto-Loeschung (Art. 17 DSGVO).
- Datenmengen einzelner Nutzer sind klein; das ZIP wird im Speicher erzeugt.
  Fuer die potenziell laengste Liste (Sitzungen) streamt die CSV zeilenweise.
