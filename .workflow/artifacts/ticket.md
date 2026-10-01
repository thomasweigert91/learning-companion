# Ticket: Dashboard und Auswertung der Lernaktivitaet

## 1. Problem / Ziel

Die Anwendung speichert Lernziele (`Goal`), Lernsitzungen (`LearningSession`) und
Tags, bietet aber keine zusammenfassende Sicht darauf. Wer wissen will, wie viele
Ziele noch offen sind, in welchen Themen die meiste Zeit steckt oder ob die
Lernmenge ueber die Wochen stabil bleibt, muss die Listenansichten manuell
durchzaehlen.

Dieses Ticket ergaenzt ein Dashboard unter `/dashboard/`, das genau diese drei
Fragen beantwortet. Die Kennzahlen werden vollstaendig per Django-ORM-Aggregation
auf der Datenbank berechnet (kein Auszaehlen in Python), und zwar ausschliesslich
ueber die Daten des angemeldeten Nutzers.

Fachliche Kennzahlen:

1. **Ziele nach Status** -- Anzahl der `Goal`-Objekte gruppiert nach `status`
   (`planned`, `in-progress`, `done`) via `Count()`.
2. **Lernzeit je Tag-Kategorie** -- Summe von `LearningSession.duration` gruppiert
   nach dem zugeordneten `Tag` via `Sum('duration')`.
3. **Lernzeit je Kalenderwoche** -- Summe von `LearningSession.duration` gruppiert
   nach `TruncWeek('date')` via `Sum('duration')`.

## 2. Akzeptanzkriterien

- [ ] Es existiert eine `DashboardView` unter dem Pfad `/dashboard/` mit dem
      URL-Namen `core:dashboard`.
- [ ] Die View ist ausschliesslich fuer angemeldete Nutzer erreichbar
      (`LoginRequiredMixin` bzw. `@login_required`); ein anonymer Aufruf von
      `/dashboard/` fuehrt zu einem Redirect (302) auf die Login-Seite.
- [ ] `base.html` enthaelt im Navigations-Bereich fuer angemeldete Nutzer einen
      Link "Dashboard" auf `{% url 'core:dashboard' %}`.
- [ ] Die Kennzahl "Ziele nach Status" liefert fuer jeden der drei Status-Werte
      (`planned`, `in-progress`, `done`) die korrekte Anzahl der Goals von
      `request.user`, berechnet per `.values('status').annotate(Count(...))`.
      Ein Status ohne Goals wird mit dem Wert 0 ausgewiesen und nicht verschluckt.
- [ ] Die Kennzahl "Lernzeit je Tag-Kategorie" liefert pro `Tag` die Summe der
      `duration`-Werte aller Sessions von `request.user`, berechnet per
      `.values('tags__name').annotate(Sum('duration'))`. Eine Session mit mehreren
      Tags zaehlt in jede dieser Kategorien ein.
- [ ] Die Kennzahl "Lernzeit je Kalenderwoche" liefert pro Kalenderwoche die Summe
      der `duration`-Werte aller Sessions von `request.user`, berechnet per
      `.annotate(woche=TruncWeek('date')).values('woche').annotate(Sum('duration'))`,
      aufsteigend nach Woche sortiert.
- [ ] Zusaetzlich weist das Dashboard als KPI-Kacheln aus: Gesamtzahl der Goals,
      Gesamtzahl der Sessions und die insgesamt erfasste Lernzeit (Summe aller
      `duration`-Werte) des angemeldeten Nutzers.
- [ ] Das Template `core/dashboard.html` stellt die KPIs als Kacheln dar und die
      drei Auswertungen als Tabellen, jeweils ergaenzt um einen reinen CSS-Balken,
      dessen Breite proportional zum Maximalwert der jeweiligen Auswertung ist.
- [ ] Hat der Nutzer noch keine Sessions bzw. Goals, zeigt das Dashboard statt
      leerer Tabellen eine verstaendliche Hinweiszeile an und wirft keinen Fehler
      (insbesondere keine Division durch Null bei der Balkenbreite).
- [ ] Ein Test verifiziert die Status-Zaehlung gegen eine bekannte Datenlage
      (konkrete Soll-Zahlen, nicht nur "ist nicht leer").
- [ ] Ein Test verifiziert die Summe je Tag-Kategorie gegen bekannte
      `duration`-Werte.
- [ ] Ein Test verifiziert die Summe je Kalenderwoche gegen bekannte Daten ueber
      mindestens zwei verschiedene Kalenderwochen hinweg.
- [ ] Ein Isolations-Test belegt: Goals und Sessions eines zweiten Nutzers
      veraendern keine der Kennzahlen des angemeldeten Nutzers. Dazu wird fuer
      beide Nutzer dieselbe Datenlage angelegt und geprueft, dass die Zahlen des
      ersten Nutzers unveraendert bleiben.
- [ ] Ein Test belegt, dass ein Nutzer ohne jede Datenlage das Dashboard mit
      Status 200 und Nullwerten erhaelt.
- [ ] Alle bestehenden Tests laufen weiterhin durch (`python manage.py test`).

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Django 5 mit dem bestehenden `core`-App-Layout; Entwicklung gegen SQLite im
  aktiven `.venv`.
- Die Aggregation erfolgt vollstaendig im ORM (`Count`, `Sum`, `TruncWeek` aus
  `django.db.models` bzw. `django.db.models.functions`). Es wird **nicht** in
  Python ueber Querysets iteriert, um Werte aufzusummieren.
- Das User-Scoping folgt der bestehenden Konvention: Goals ueber `user=request.user`,
  Sessions ueber `goal__user=request.user`. Der Besitzer wird bei Sessions
  weiterhin nicht redundant gespeichert.
- Es werden **keine** Modell-Aenderungen und damit keine neuen Migrationen
  vorgenommen; alle benoetigten Felder existieren bereits.
- Das Frontend bleibt bei reinem CSS im Stil von `base.html` (das Projekt nutzt
  bewusst kein CSS-Framework); die Balken sind `div`-Elemente mit prozentualer
  Breite.
- `TruncWeek` liefert ein `date`-Objekt (Wochenbeginn). Dieses wird im Template
  als Wochenbeginn formatiert ausgegeben.
- Tests liegen als `core/tests/test_dashboard.py` neben den bestehenden
  Testmodulen und folgen deren Aufbau.

**Out-of-Scope**

- Keine Diagramm-Bibliothek (Chart.js, matplotlib o. ae.) und kein Bootstrap.
- Kein Export der Auswertungen (CSV, PDF) und keine Druckansicht.
- Keine Filter- oder Zeitraum-Auswahl auf dem Dashboard; es wird immer die
  vollstaendige Historie ausgewertet.
- Keine JSON-/REST-API-Endpunkte fuer die Kennzahlen.
- Keine Auswertung der Ressourcen (`Resource`) und keine KI-Zusammenfassung des
  Dashboards.
- Kein Caching der Aggregate.
