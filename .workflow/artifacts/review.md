# Code Review: Dashboard und Auswertung der Lernaktivitaet

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, SQLite. **145 Tests** (122 aus Feature 1–4 + 23 neue), `validate_code.ps1` grün (Exit-Code 0).

Geänderte/neue Dateien:

- Neu: `core/templates/core/dashboard.html`, `core/tests/test_dashboard.py`
- Geändert: `core/views.py` (+95 Zeilen, rein additiv), `core/urls.py`, `core/templates/base.html`

---

## 1. Abdeckung der Akzeptanzkriterien

### View und Zugriffsschutz

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `DashboardView` unter `/dashboard/`, URL-Name `core:dashboard` | `core/urls.py:11`, `core/views.py:334` | ja |
| 2 | Nur für angemeldete Nutzer; anonym → Redirect auf Login | `LoginRequiredMixin` (`views.py:334`); `test_anonym_wird_umgeleitet` prüft `assertRedirects` inkl. `?next=` | ja |
| 3 | Nav-Link "Dashboard" in `base.html` im Authenticated-Block | `base.html:55`; `test_navbar_enthaelt_dashboard_link` prüft gegen eine *andere* Seite (`/goals/`), nicht gegen das Dashboard selbst | ja |

### Aggregation

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 4 | Goals je Status via `Count()`, auf `request.user` gefiltert | `goals_nach_status()` (`views.py:350`): `.values_list("status").annotate(Count("pk"))` | ja |
| 5 | Status ohne Goals wird mit 0 ausgewiesen, nicht verschluckt | Die Liste wird über `Goal.Status.choices` aufgebaut, das Queryset liefert nur die Füllwerte; `test_status_ohne_goals_wird_mit_null_ausgewiesen` (`done` = 0 bei Nutzer A) | ja |
| 6 | Lernzeit je Tag-Kategorie via `Sum('duration')` | `zeit_je_tag()` (`views.py:360`): `.values("tags__name").annotate(Sum("duration"))` | ja |
| 7 | Session mit mehreren Tags zählt in jede Kategorie ein | Die 30-Minuten-Session trägt Python **und** Django; `test_summe_je_tag` erwartet 90/75 — ohne Doppelzählung wären es 60/45 | ja |
| 8 | Lernzeit je Kalenderwoche via `TruncWeek('date')` + `Sum`, aufsteigend | `zeit_je_woche()` (`views.py:375`); `test_summe_je_kalenderwoche`, `test_aufsteigend_sortiert` | ja |
| 9 | KPIs: Goals gesamt, Sessions gesamt, Minuten gesamt | `get_context_data()` (`views.py:390`); `test_kpi_summen` (3 / 4 / 155) | ja |
| 10 | Keine Aggregation in Python | Alle Summen/Zählungen stammen aus `Count`/`Sum`/`aggregate`. Die einzigen Python-Schleifen sind das Auffüllen fehlender Status-Werte und die `max(...)`-Bestimmung der Balken-Bezugsgröße — beides Darstellungslogik, keine Kennzahlberechnung | ja |

### Frontend

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 11 | KPI-Kacheln + drei Tabellen mit proportionalen CSS-Balken | `dashboard.html`; `.kpi-row`/`.kpi-card`/`.bar-track`/`.bar` in `base.html:22-41` | ja |
| 12 | Hinweiszeile statt leerer Tabelle; keine Division durch Null | Jeder Abschnitt ist in `{% if %}` auf seine Bezugsgröße gehüllt; `test_hinweis_statt_leerer_tabelle`, `test_maxima_sind_null_und_verursachen_keinen_fehler` | ja |

### Tests

| # | Kriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 13 | Status-Zählung gegen konkrete Soll-Zahlen | `test_zaehlung_je_status` vergleicht das vollständige Dict gegen `{planned: 2, in-progress: 1, done: 0}` — kein "ist nicht leer" | ja |
| 14 | Tag-Summen gegen bekannte Werte | `test_summe_je_tag`: `{Python: 90, Django: 75}` | ja |
| 15 | Wochen-Summen über ≥ 2 Kalenderwochen | `test_summe_je_kalenderwoche`: KW ab 14.09.2026 = 90, KW ab 21.09.2026 = 65 | ja |
| 16 | Isolations-Nachweis gegen Fremddaten | `IsolationsTests`, 5 Testfälle; siehe Abschnitt 2 | ja |
| 17 | Nutzer ohne Datenlage: 200 + Nullwerte | `LeeresDashboardTests`, 4 Testfälle | ja |
| 18 | Bestehende Tests laufen weiter | 145/145 grün, davon 122 vorbestehend | ja |

---

## 2. Sicherheit: Mandantentrennung und Auth

**Auth-Bypass:** Kein Pfad an `LoginRequiredMixin` vorbei. Die View ist `TemplateView` ohne PK-Parameter, es gibt also keine fremdadressierbare Route — strukturell dieselbe Lösung wie bei `ProfileDetailView`.

**Scoping:** Beide Einstiegspunkte sind zentralisiert (`get_goals()` → `user=request.user`, `get_sessions()` → `goal__user=request.user`, `views.py:344-348`). Jede Aggregation geht durch diese zwei Methoden; es existiert kein unscoped `objects.all()` in der View. Die Konvention "Besitzer der Session wird über `goal__user` aufgelöst, nicht redundant gespeichert" ist eingehalten.

**Mutationsprobe (vom Reviewer durchgeführt):** Beide Filter wurden testweise durch `objects.all()` ersetzt. Ergebnis: **15 der 23 Tests schlagen fehl**, darunter alle fünf Isolations-Tests. Die Tests prüfen das Scoping also tatsächlich und sind nicht nur gegen sich selbst konsistent. Der Originalzustand wurde anschließend wiederhergestellt (`git diff` auf `core/views.py`: rein additiv, 95 Einfügungen, keine geänderten Bestandszeilen) und die volle Suite erneut grün ausgeführt.

Dass die Probe greift, liegt an der Testdatenlage: Nutzer B hat **dieselben Tags und dieselben Kalenderwochen**, aber deutlich andere Dauern (500/700 statt 60/30/45/20). Ein fehlender Filter verschiebt damit zwangsläufig jede einzelne Kennzahl. Eine Datenlage mit disjunkten Tags hätte den Fehler stillschweigend durchgelassen — der Plan hat das korrekt vorweggenommen.

**SQL-Injection:** Kein `raw()`, kein `extra()`, keine String-Interpolation in Querysets. Ausschließlich ORM-Ausdrücke mit parametrisierten Werten.

**XSS:** Keine `|safe`-Filter und kein `autoescape off` im neuen Template. Die einzige nutzerbeeinflusste Ausgabe ist `{{ zeile.tags__name }}` und wird regulär escaped. Der `style="width: …%"`-Wert stammt aus `{% widthratio %}` und ist damit strukturell immer eine Zahl — keine Injektion über Attributwerte möglich.

---

## 3. Code-Qualität

**Positiv:**

- Die View zerlegt die Aggregation in vier benannte Methoden statt eines 40-zeiligen `get_context_data()`. Jede Methode ist einzeln les- und überschreibbar.
- Zwei nicht offensichtliche Fallstricke sind im Code kommentiert statt stillschweigend umgangen:
  - `tags__isnull=False` (`views.py:366`) gegen die `None`-Gruppe aus dem LEFT JOIN auf die M2M-Tabelle.
  - `.order_by()` am Ende von `zeit_je_woche()` (`views.py:386`) — ohne das zieht `Meta.ordering = ["-date", "-pk"]` das Feld `pk` in die GROUP-BY-Klausel und zerlegt die Gruppierung in Einzelzeilen. Das ist der klassische Django-Aggregationsfehler; er ist hier vermieden **und** begründet.
  - `aggregate(...)["gesamt"] or 0` (`views.py:404`) gegen das `None` bei leerer Datenlage.
- Die Erwartungswerte der Tests stehen als Klassenkonstanten an einer Stelle (`test_dashboard.py:34-43`) statt als Magic Numbers über 15 Testmethoden verteilt.
- Benennung und Kommentarstil (deutsch, ohne Umlaute im Code) folgen den Bestandsmodulen.

**Keine Befunde zu:** totem Code, auskommentierten Resten, ungenutzten Importen, Shadowing, Formatierung.

**Zwei Anmerkungen ohne Nachbesserungsbedarf:**

1. *Query-Anzahl.* Ein Seitenaufruf setzt sechs Queries ab (drei Gruppierungen, zwei `count()`, ein `aggregate`). Das ist für das Feature angemessen; Caching ist im Ticket explizit out-of-scope. Erst bei deutlich größeren Datenmengen lohnt ein Zusammenziehen — dann aber auf Kosten der Lesbarkeit.
2. *`max()` in Python statt in der DB.* Die Bezugsgröße der Balken wird über die bereits geladene Ergebnisliste bestimmt, nicht per zusätzlichem `aggregate(Max(...))`. Das spart eine Query und arbeitet auf Daten, die ohnehin im Speicher sind — die Kennzahl selbst wird dadurch nicht berechnet, nur skaliert.

---

## 4. Abweichungen gegenüber dem Plan

| Abweichung | Bewertung |
|---|---|
| Die Testdatenlage wurde um eine **Session ohne Tag** (20 Min, Woche 2) erweitert; Soll-Werte dadurch 65 statt 45 Minuten in Woche 2, 155 statt 135 gesamt, 4 statt 3 Sessions. | Verbesserung. Sie belegt gleichzeitig, dass der LEFT JOIN keine `None`-Kategorie erzeugt und die Zeit trotzdem in Wochen- und Gesamtsumme einfließt. `plan.md` wurde entsprechend nachgezogen, Plan und Code sind konsistent. |
| Zusätzlich `max_status_anzahl` im Kontext und ein Balken auch in der Status-Tabelle. | Konsistenz mit den beiden anderen Tabellen; vom Ticket gedeckt ("Darstellung als übersichtliche Tabellen oder CSS-Balken"). |
| Zusätzliche Testfälle über den Plan hinaus (Sortierung, Montags-Prüfung, Gegenprobe Nutzer B, Konsistenz Wochensummen ↔ Gesamtzeit). | Erweiterung, keine Lücke. |
| Bootstrap aus der Feature-Beschreibung wurde **nicht** eingeführt; stattdessen reines CSS. | Korrekt. `base.html` hält ausdrücklich fest: "bewusst ohne CSS-Framework". Ein Framework allein für dieses Feature hätte die Bestandsarchitektur gebrochen. Im Ticket als Rahmenbedingung festgehalten. |

---

## 5. Migrationen

Keine Modell-Änderung, keine neue Migration. `python manage.py makemigrations --check --dry-run` meldet "No changes detected" — der erzeugte Zustand ist also nicht nur ungetestet migrationsfrei, sondern nachweislich.

---

## 6. Verifikation

```powershell
python manage.py check                              # 0 Issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test                               # Ran 145 tests — OK
.\.workflow\hooks\validate_code.ps1                 # Exit-Code 0
```

Ergänzend vom Reviewer: Mutationsprobe am User-Scoping (Abschnitt 2) — 15 Fehlschläge, anschließend sauber zurückgesetzt und erneut grün.

---

## 7. Fazit

Alle 18 Akzeptanzkriterien des Tickets sind erfüllt und jeweils durch einen benannten Test oder eine konkrete Codestelle belegt. Die Aggregation läuft vollständig im ORM, das User-Scoping ist zentralisiert und durch eine Mutationsprobe als wirksam nachgewiesen. Keine Sicherheitsbefunde, keine toten Pfade, keine Nachbesserungspunkte.

**Freigabe erteilt: APPROVED.**
