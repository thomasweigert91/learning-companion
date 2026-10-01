# Ticket: UI- und Styling-Upgrade auf Bootstrap 5

## 1. Problem / Ziel

Die Oberflaeche der Anwendung besteht aus ungestyltem HTML: Formulare werden per
`{{ form.as_p }}` ausgegeben, Listen als nackte `<ul>`, die Navigation als lose
Reihe von Links. Funktional ist alles vorhanden, die App wirkt aber unfertig,
ist auf Mobilgeraeten muehsam zu bedienen und gibt kaum visuelle Orientierung
(aktuelle Seite, Status eines Ziels, Fehlerzustaende).

Dieses Ticket stellt **alle Seiten** auf ein einheitliches, responsives
Bootstrap-5-Design um -- Navigation, Startseite, Auth, Profil, Dashboard, Goals,
Sessions und Resources. Es ist ein reines Darstellungs-Feature: URLs,
Formularfelder, Feldnamen, HTML-IDs und das Verhalten der Views bleiben
unveraendert.

**Bewusste Abkehr von einer frueheren Entscheidung:** In Feature 5 wurde das
Dashboard noch "bewusst ohne CSS-Framework" gebaut, weil ein Framework fuer ein
einzelnes Feature die Architektur gebrochen haette. Mit diesem Ticket wird das
Framework fuer die **gesamte** Oberflaeche eingefuehrt; die handgeschriebenen
Dashboard-Styles (`.kpi-card`, `.bar` usw.) werden dabei ersetzt, nicht
parallel weitergefuehrt.

## 2. Akzeptanzkriterien

### Einbindung

- [ ] `base.html` bindet Bootstrap **5.3.8** (CSS + `bootstrap.bundle.min.js`)
      und Bootstrap Icons **1.13.1** per jsDelivr-CDN ein.
- [ ] Alle drei CDN-Ressourcen tragen ein `integrity`-Attribut (SHA-384, aus den
      tatsaechlich ausgelieferten Dateien berechnet) und `crossorigin="anonymous"`.
- [ ] Das Bundle-Script wird am Ende von `<body>` geladen und blockiert damit
      nicht das Rendern.

### Navigation

- [ ] Responsive Navbar (`navbar-expand-lg`) mit Toggler; unterhalb von `lg`
      klappt die Navigation in ein Collapse-Menue.
- [ ] Fuer angemeldete Nutzer: Links **Dashboard**, **Goals**, **Sessions**.
      Der Link des aktuellen Bereichs ist hervorgehoben (`.active`) **und**
      traegt `aria-current="page"`. Zum Bereich "Goals" zaehlen auch
      Goal-Detail/-Formulare und die Resource-Routen, zu "Sessions" alle
      Session-Routen.
- [ ] User-Dropdown rechts mit dem Benutzernamen, darin "Mein Profil",
      "Profil bearbeiten" und "Logout". Logout bleibt ein **POST**-Formular mit
      CSRF-Token (Django 5 akzeptiert kein GET-Logout).
- [ ] Fuer anonyme Nutzer: "Login" und "Registrieren" statt des Dropdowns.
- [ ] Der bestehende Test `test_navbar_enthaelt_dashboard_link`
      (`href="/dashboard/"`) bleibt gruen.

### Layout & Komponenten

- [ ] Inhalte liegen in einem `container` mit responsivem vertikalem Spacing;
      Django-Messages erscheinen als schliessbare Bootstrap-Alerts, wobei der
      Message-Level `error` auf `alert-danger` abgebildet wird.
- [ ] **Auth (Login, Registrierung):** zentrierte Card, volle Button-Breite,
      Formularfelder als `form-control` mit zugeordnetem `<label>`.
- [ ] **Profil-Ansicht:** Card mit Initialen-Avatar, Name, Cohort und den Focus
      Areas als Badges; Button "Profil bearbeiten".
- [ ] **Profil-Bearbeiten, Goal-Formular, Session-Formular:** Formular in einer
      Card; Mehrfachauswahlen (Focus Areas, Tags) als `<fieldset>` mit
      `<legend>`, die Checkboxen als anklickbare Chips.
- [ ] **Dashboard:** drei KPI-Statistikkarten mit Icon; die drei Auswertungen
      als Tabellen in Cards; die bisherigen CSS-Balken werden durch Bootstrap-
      `progress`-Balken ersetzt. Die Leerzustands-Texte bleiben **wortgleich**.
- [ ] **Goals-Liste:** Status-Filter als `form-select` (ID `status` bleibt),
      Goals als responsives Card-Grid mit farbigem Status-Badge und den
      Aktions-Buttons Details / Bearbeiten / Loeschen.
- [ ] **Goal-Detail:** Kopfbereich mit Titel, Status-Badge und Aktionen;
      Sessions als Tabelle; Ressourcen als List-Group mit Typ-Badge; KI-Bereich
      als eigene Card.
- [ ] **Sessions-Liste:** Uebersichtstabelle mit Datum, Lernziel, Dauer und den
      Tags als Badges. Die Tags werden per `prefetch_related("tags")` geladen,
      damit die Tabelle keine N+1-Abfragen erzeugt.
- [ ] **Session-Detail & Loesch-Bestaetigungen:** Card-Layout; destruktive
      Aktionen als `btn-danger`, Abbrechen als sekundaerer Button.
- [ ] **Startseite:** Hero-Bereich fuer anonyme Nutzer, Schnellzugriffs-Cards fuer
      angemeldete Nutzer.

### Formulare

- [ ] Formularfelder werden ueber **ein** wiederverwendbares Partial gerendert,
      das je nach Widget-Typ `form-control`, `form-select` oder
      `form-check-input` vergibt -- ohne `forms.py` anzufassen.
- [ ] Feldfehler stehen direkt unter dem Feld (`invalid-feedback`), das Feld
      erhaelt `is-invalid` und `aria-invalid="true"`; ueber `aria-describedby`
      sind Fehlertext und Hilfetext mit dem Feld verknuepft.
- [ ] Pflichtfelder sind visuell markiert, der Hinweis darauf steht am Formular.

### Barrierefreiheit

- [ ] Skip-Link "Zum Inhalt springen" als erstes fokussierbares Element.
- [ ] Alle rein dekorativen Icons tragen `aria-hidden="true"`; Buttons, die nur
      ein Icon zeigen, haben ein `aria-label` bzw. einen `visually-hidden`-Text.
- [ ] Tabellen haben `<th scope="col">` und eine (ggf. visuell versteckte)
      `<caption>`.
- [ ] Progress-Balken tragen `role="progressbar"`, `aria-label` und
      `aria-valuenow`/`-min`/`-max`.
- [ ] Links mit `target="_blank"` kuendigen das neue Fenster fuer Screenreader an.
- [ ] Jede Seite hat genau eine `<h1>`; Status wird nie **nur** ueber Farbe
      transportiert (Badges enthalten immer den Text).

### Regressionsschutz

- [ ] Alle **145** bestehenden Tests laufen unveraendert gruen; es wird kein Test
      angepasst, um ihn gruen zu bekommen.
- [ ] Keine Aenderung an URLs, Formularfeldern oder Feldnamen; alle bisherigen
      expliziten HTML-IDs (`status`) und die von Tests gepruefte CSS-Klasse
      `badge-{typ}` bleiben erhalten.
- [ ] Die Texte "Fortschrittszusammenfassung" und "Naechste Lernschritte"
      erscheinen weiterhin **nur**, wenn ein KI-Ergebnis vorliegt
      (`test_ai_views` prueft deren Abwesenheit).
- [ ] Neue Tests sichern die Kernpunkte des Redesigns ab: Bootstrap-Einbindung
      mit SRI, aktiver Nav-Link mit `aria-current`, Logout als POST im Dropdown,
      Formular-Fehlerdarstellung mit `is-invalid`/`aria-invalid` und die
      Template-Tags/-Filter.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Bootstrap 5.3.8 und Bootstrap Icons 1.13.1 ausschliesslich per CDN, keine
  lokale Kopie und kein Build-Schritt (kein npm, kein Sass).
- Die Formular-Klassen werden ueber einen Template-Filter in
  `core/templatetags/` vergeben, nicht ueber `widgets`/`attrs` in `forms.py`.
  Damit erfasst die Loesung auch Django-eigene Formulare wie das
  `AuthenticationForm` des Logins, ohne die URL-Konfiguration zu aendern.
- Die einzige Aenderung an Python-Code ausserhalb von `templatetags/` ist das
  `prefetch_related("tags")` in der Session-Liste.
- Die bestehende Textkonvention der Templates (Umlaute als `ae`/`oe`/`ue`)
  bleibt erhalten; mehrere Tests pruefen exakte Texte.
- Ohne Internetzugang laedt kein Styling; die Anwendung bleibt aber voll
  funktionsfaehig (reines HTML mit nativen Formularen, Logout als normales
  POST-Formular).

**Out-of-Scope**

- Kein Dark-Mode und kein Theme-Umschalter.
- Kein Austausch der Texte gegen echte Umlaute und keine Internationalisierung.
- Keine JavaScript-Interaktion ueber Bootstraps eigene Komponenten hinaus
  (keine Modals fuer Loesch-Bestaetigungen, kein AJAX).
- Kein Redesign des Django-Admins.
- Keine eigenen Grafiken, Logos oder Webfonts ueber die Bootstrap Icons hinaus.
- Keine Aenderungen an Modellen, Formularen, URLs oder Migrationen.
