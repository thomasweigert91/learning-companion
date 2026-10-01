# Implementierungs-Plan: Dashboard und Auswertung der Lernaktivitaet

## 1. Betroffene Dateien

- Neu: `core/templates/core/dashboard.html`
- Neu: `core/tests/test_dashboard.py`
- Ändern: `core/views.py` (neue `DashboardView`)
- Ändern: `core/urls.py` (Route `dashboard/` -> `core:dashboard`)
- Ändern: `core/templates/base.html` (Navigations-Link + CSS fuer Kacheln/Balken)

## 2. Datenmodelle & Migrationen

**Keine.** Das Feature ist rein lesend. Alle benoetigten Felder existieren bereits:

| Modell | genutzte Felder | Rolle in der Auswertung |
| --- | --- | --- |
| `Goal` | `user`, `status` | Gruppierung "Ziele nach Status" |
| `LearningSession` | `goal` (-> `goal__user`), `date`, `duration`, `tags` | Basis beider Zeit-Auswertungen |
| `Tag` | `name` (ueber `LearningSession.tags`) | Gruppierung "Lernzeit je Tag-Kategorie" |

Es werden **keine** Felder ergaenzt und **keine** Migration erzeugt.
`python manage.py makemigrations --check` muss folglich sauber bleiben.

**Scoping-Konvention (unveraendert uebernommen):**

- Goals: `Goal.objects.filter(user=request.user)`
- Sessions: `LearningSession.objects.filter(goal__user=request.user)` --
  der Besitzer wird weiterhin nicht redundant auf der Session gespeichert.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Setup & Models** -- Verifizieren, dass keine Modell-Aenderung
      noetig ist (`makemigrations --check`). In `core/views.py` die Importe
      ergaenzen: `from django.db.models import Count, Sum` und
      `from django.db.models.functions import TruncWeek`.

- [ ] **Schritt 2: Business-Logik / Views** -- `DashboardView(LoginRequiredMixin,
      TemplateView)` mit `template_name = "core/dashboard.html"` anlegen. Die
      Aggregation wird in vier kleine, je einzeln testbare Hilfsmethoden
      zerlegt, die alle `request.user` als Grundlage haben:

      1. `_goals_nach_status()`
         ```python
         roh = dict(
             Goal.objects.filter(user=self.request.user)
             .values_list("status")
             .annotate(anzahl=Count("pk"))
         )
         return [
             {"status": wert, "label": label, "anzahl": roh.get(wert, 0)}
             for wert, label in Goal.Status.choices
         ]
         ```
         Die Schleife ueber `Goal.Status.choices` sorgt dafuer, dass ein Status
         ohne Goals mit 0 erscheint statt zu fehlen. Gezaehlt wird weiterhin in
         der Datenbank (`Count`), nicht in Python.

      2. `_zeit_je_tag()`
         ```python
         LearningSession.objects.filter(goal__user=user, tags__isnull=False)
             .values("tags__name")
             .annotate(minuten=Sum("duration"))
             .order_by("-minuten", "tags__name")
         ```
         `tags__isnull=False` verhindert die `None`-Gruppe aus dem LEFT JOIN auf
         die M2M-Tabelle. Eine Session mit mehreren Tags erzeugt mehrere
         Join-Zeilen und zaehlt damit korrekt in jede Kategorie ein.

      3. `_zeit_je_woche()`
         ```python
         LearningSession.objects.filter(goal__user=user)
             .annotate(woche=TruncWeek("date"))
             .values("woche")
             .annotate(minuten=Sum("duration"))
             .order_by("woche")
         ```
         `TruncWeek` liefert den Montag der jeweiligen Woche als `date`.
         Wichtig: `.order_by()` muss nach `.values()` gesetzt werden, sonst
         zieht `Meta.ordering = ["-date", "-pk"]` das Feld `pk` in die
         GROUP-BY-Klausel und sprengt die Gruppierung.

      4. `_kpis()` -- `Goal.objects.filter(...).count()`,
         `sessions.count()` und
         `sessions.aggregate(gesamt=Sum("duration"))["gesamt"] or 0`
         (das `or 0` faengt das `None` bei leerer Datenlage ab).

      `get_context_data()` legt zusaetzlich zu den Listen jeweils den
      Maximalwert (`max_tag_minuten`, `max_wochen_minuten`) in den Kontext --
      berechnet mit `max(..., default=0)`. Daraus bestimmt das Template die
      Balkenbreite; ist das Maximum 0, wird gar keine Tabelle gerendert, womit
      eine Division durch Null strukturell ausgeschlossen ist.

- [ ] **Schritt 3: UI / Templates** -- `core/templates/core/dashboard.html`
      anlegen (`{% extends "base.html" %}`):
      - KPI-Kacheln (Goals gesamt, Sessions gesamt, Lernzeit gesamt) als
        `div.kpi-card` in einem `div.kpi-row`.
      - Drei Abschnitte mit je einer `<table>`; in der letzten Spalte ein
        `div.bar` mit `style="width: {% widthratio wert maximum 100 %}%"`.
        `widthratio` ist der Django-Bordmittel-Weg fuer die Prozentrechnung und
        gibt bei Nenner 0 einen leeren String zurueck -- zusammen mit der
        `{% if %}`-Huelle doppelt abgesichert.
      - Pro Abschnitt ein `{% empty %}`- bzw. `{% if %}`-Zweig mit einer
        Hinweiszeile ("Noch keine Lernsitzungen erfasst.").
      - Wochen-Spalte via `{{ zeile.woche|date:"d.m.Y" }}` als Wochenbeginn.

      In `base.html` den Nav-Link `<a href="{% url 'core:dashboard' %}">Dashboard</a>`
      im `{% if user.is_authenticated %}`-Block ergaenzen (vor "Goals") und den
      bestehenden `<style>`-Block um `.kpi-row`, `.kpi-card`, `.bar` und
      `.bar-track` erweitern -- reines CSS, kein Framework, passend zum
      bestehenden Badge-Stil.

      In `core/urls.py` ergaenzen:
      `path("dashboard/", views.DashboardView.as_view(), name="dashboard")`.

- [ ] **Schritt 4: Tests** -- `core/tests/test_dashboard.py` nach dem Muster von
      `core/tests/test_scoping.py` mit einer gemeinsamen
      `DashboardDatenTestCase(TestCase)`-Basis (`setUpTestData`):
      - Nutzer A: 2 Goals `planned`, 1 Goal `in-progress`, 0 Goals `done`.
      - Tags `Python` und `Django`.
      - Sessions von A: 60 Min (Tag Python) und 30 Min (Tags Python + Django) in
        Woche 1, 45 Min (Tag Django) sowie 20 Min **ohne Tag** in Woche 2.
        Erwartet: Python 90, Django 75; Woche 1 = 90, Woche 2 = 65; gesamt 155
        bei 4 Sessions. Die taglose Session belegt zugleich, dass der LEFT JOIN
        keine `None`-Kategorie erzeugt, die Zeit aber in Wochen- und
        Gesamtsumme einfliesst.
      - Nutzer B bekommt eine **spiegelbildliche** Datenlage mit anderen Werten,
        damit ein fehlendes Scoping die Zahlen von A nachweislich verschoebe.

- [ ] **Schritt 5: Validierung** -- `python manage.py check`,
      `python manage.py makemigrations --check --dry-run` und
      `python manage.py test` im aktiven `.venv` ausfuehren, anschliessend
      `.\.workflow\hooks\validate_code.ps1`.

## 4. Validierung & Test-Strategie

**Testmodul:** `core/tests/test_dashboard.py`

| Testklasse | Testfall | Prueft |
| --- | --- | --- |
| `DashboardZugriffTests` | `test_anonym_wird_umgeleitet` | `GET /dashboard/` ohne Login -> `assertRedirects` auf `login?next=/dashboard/` |
| | `test_angemeldet_erreichbar` | Status 200 und Template `core/dashboard.html` |
| | `test_navbar_enthaelt_dashboard_link` | `/goals/` enthaelt `href="/dashboard/"` fuer angemeldete Nutzer |
| `GoalsNachStatusTests` | `test_zaehlung_je_status` | Kontext `goals_nach_status` liefert exakt `planned=2`, `in-progress=1`, `done=0` |
| | `test_status_ohne_goals_wird_mit_null_ausgewiesen` | alle drei Status-Werte sind enthalten, auch der leere |
| `ZeitJeTagTests` | `test_summe_je_tag` | `Python = 90`, `Django = 75` (Mehrfach-Tag zaehlt in beide Kategorien) |
| | `test_session_ohne_tag_erzeugt_keine_leere_gruppe` | kein Eintrag mit `tags__name is None` |
| `ZeitJeWocheTests` | `test_summe_je_kalenderwoche` | zwei Wochen-Eintraege mit 90 und 65 Minuten, aufsteigend nach `woche` sortiert |
| | `test_wochenbeginn_ist_montag` | `TruncWeek` liefert den Montag der jeweiligen Woche |
| `KpiTests` | `test_kpi_summen` | `goals_gesamt=3`, `sessions_gesamt=4`, `minuten_gesamt=155` |
| `IsolationsTests` | `test_fremde_goals_aendern_status_zaehlung_nicht` | Nutzer A sieht trotz Goals von B weiterhin 2/1/0 |
| | `test_fremde_sessions_aendern_tag_summen_nicht` | Tag-Summen von A bleiben 90/75 |
| | `test_fremde_sessions_aendern_wochen_summen_nicht` | Wochen-Summen von A bleiben 90/65 |
| | `test_fremde_daten_aendern_kpis_nicht` | `minuten_gesamt` von A bleibt 155 |
| `LeeresDashboardTests` | `test_nutzer_ohne_daten` | frischer Nutzer: Status 200, alle KPIs 0, leere Listen, keine Exception |
| | `test_hinweis_statt_leerer_tabelle` | Response enthaelt den Hinweistext |

**Begruendung der Isolations-Strategie:** Ein Scoping-Fehler faellt nur auf, wenn
die Fremddaten die Kennzahlen veraendern wuerden. Deshalb bekommt Nutzer B
Sessions mit *anderen* Dauern und dieselben Tags -- ein fehlendes
`goal__user=`-Filter wuerde die Tag-Summe von A sofort nach oben ziehen und den
Test rot faerben.

**Kommandos** (im aktiven `.venv`):

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

**Abnahmekriterium:** `validate_code.ps1` endet mit Exit-Code 0, d. h. System-Check
und die komplette Test-Suite (bestehende Module inklusive) laufen gruen durch.
