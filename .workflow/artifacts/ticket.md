# Ticket: Persistente KI-Historie zu Lernzielen

## 1. Problem / Ziel

Die KI-Aktionen "Zusammenfassung generieren" und "Naechste Schritte vorschlagen"
legen ihr Ergebnis bisher nur in der **Session** ab. Das hat drei Folgen:

- Nach Logout, Session-Ablauf oder Browserwechsel ist das Ergebnis verloren.
- Pro Goal und Typ existiert immer nur das **letzte** Ergebnis; jede neue Anfrage
  ueberschreibt die vorherige. Ein Verlauf -- etwa wie sich die Einschaetzung
  ueber die Wochen veraendert hat -- ist nicht nachvollziehbar.
- Seit dem echten API-Anschluss kostet jede Anfrage Geld. Ein Ergebnis, das beim
  naechsten Login weg ist, muss erneut bezahlt werden.

Dieses Ticket speichert jedes erfolgreich erzeugte KI-Ergebnis dauerhaft in der
Datenbank und zeigt alle Ergebnisse eines Goals als chronologische Historie auf
der Goal-Detailseite. Einzelne Eintraege und der gesamte Verlauf eines Goals
lassen sich loeschen -- ausschliesslich durch den Besitzer des Goals.

**Bewusste Vertragsaenderung:** Feature 4 hat per Test festgeschrieben, dass
KI-Ergebnisse *nicht* in der Datenbank landen
(`test_results_are_not_persisted_in_database`) und stattdessen in der Session
liegen. Genau diese Anforderung kehrt sich hier um. Die vier Tests, die den
Session-Speicher pruefen, werden deshalb auf den neuen Datenbank-Vertrag
umgestellt -- nicht abgeschwaecht, sondern auf das neue Verhalten gerichtet.

**Vorab-Aufgabe (im selben Durchlauf erledigt):** `settings.py` laedt die lokale
`.env` per `python-dotenv`, damit `python manage.py runserver` den API-Schluessel
ohne manuelles Setzen der Umgebung erhaelt.

## 2. Akzeptanzkriterien

### Vorab: .env-Unterstuetzung

- [ ] `python-dotenv` steht mit Versionsgrenze in `requirements.txt`;
      `settings.py` laedt `BASE_DIR / ".env"` vor dem Lesen jeder Einstellung.
- [ ] Bereits gesetzte Umgebungsvariablen haben Vorrang (`override=False`), damit
      Container und CI unveraendert aus der echten Umgebung lesen.
- [ ] Ein Testlauf erreicht **nie** das echte OpenAI-Konto, auch wenn die `.env`
      einen echten Schluessel enthaelt: ein Test-Runner erzwingt global
      `AI_MOCK_MODE=True` und einen leeren Schluessel; ein Test belegt das.

### Modell

- [ ] Neues Modell `AIFeedback` mit `goal` (ForeignKey auf `Goal`,
      `on_delete=CASCADE`, `related_name="ai_feedbacks"`), `feedback_type`
      (Choices `summary` / `next_steps`), `content` (TextField) und `created_at`
      (DateTimeField, `auto_now_add=True`).
- [ ] Standard-Sortierung: neueste zuerst (`-created_at`, `-pk` als
      Tiebreaker fuer gleiche Zeitstempel).
- [ ] Naechste Schritte werden zeilenweise in `content` abgelegt; eine Property
      `steps` liefert sie wieder als Liste.
- [ ] Wie bei `LearningSession` und `Resource` wird der Besitzer **nicht**
      redundant gespeichert, sondern immer ueber `goal__user` aufgeloest.
- [ ] Die Migration `0004_aifeedback` ist erzeugt und angewendet;
      `makemigrations --check` meldet danach keine offenen Aenderungen.
- [ ] Das Modell ist im Django-Admin registriert.

### Speichern

- [ ] Beide KI-Aktionen legen bei Erfolg **genau einen** `AIFeedback`-Eintrag mit
      dem passenden Typ an.
- [ ] Schlaegt der Aufruf fehl (`AIServiceError`), wird **nichts** gespeichert;
      die Fehlermeldung erscheint wie bisher.
- [ ] Der Session-Speicher entfaellt vollstaendig; es bleiben keine toten
      Session-Schluessel zurueck.
- [ ] `ai_service` bleibt datenbankfrei (bestehender Vertrag und Test
      `test_service_does_not_touch_database`); gespeichert wird in der View.
- [ ] Auch Ergebnisse des Mock-Modus werden gespeichert -- sie sind im Text
      bereits als "[Mock-Modus]" gekennzeichnet.

### Anzeige

- [ ] Die Goal-Detailseite zeigt in der KI-Card wie bisher das jeweils
      **neueste** Ergebnis je Typ ("Fortschrittszusammenfassung",
      "Naechste Lernschritte") -- jetzt aus der Datenbank und mit Datum.
- [ ] Darunter steht ein Abschnitt "KI-Verlauf" (Anker `#ki-verlauf`) als
      Timeline aller Eintraege, neueste zuerst, jeweils mit Datum/Uhrzeit
      (`<time datetime=...>`), Typ-Badge und formatiertem Text
      (Zusammenfassung mit Zeilenumbruechen, Schritte als nummerierte Liste).
- [ ] Ohne Eintraege zeigt der Abschnitt einen Leerzustand statt einer leeren
      Timeline.
- [ ] Die Historie wird mit einer festen Anzahl von Abfragen geladen, unabhaengig
      von der Zahl der Eintraege (keine N+1-Abfragen).
- [ ] Ergebnisse eines Goals erscheinen nie auf der Seite eines anderen Goals.

### Loeschen

- [ ] Jeder Eintrag hat einen Loeschen-Button (POST, CSRF, `aria-label` mit
      Typ und Datum); danach Redirect zurueck auf `#ki-verlauf` mit
      Erfolgsmeldung.
- [ ] "Alle zuruecksetzen" fuehrt auf eine Bestaetigungsseite (GET) und loescht
      erst per POST alle Eintraege **dieses** Goals -- Eintraege anderer Goals
      desselben Nutzers bleiben unberuehrt.
- [ ] Beide Loesch-Routen erfordern Login und liefern fuer fremde Eintraege bzw.
      fremde Goals **404**, ohne etwas zu loeschen. Ein GET auf die
      Einzel-Loesch-Route loest keine Loeschung aus (405).
- [ ] Wird ein Goal geloescht, verschwindet seine KI-Historie mit (CASCADE); die
      Loesch-Bestaetigung des Goals weist darauf hin.

### Tests

- [ ] Neue Tests belegen: Persistierung je Typ, keine Persistierung im
      Fehlerfall, Sortierung, `steps`-Property, Anzeige von Historie und
      Leerzustand, Abfrage-Anzahl unabhaengig von der Eintragszahl, Loeschen
      einzeln und gesamt, Login-Pflicht, 404 bei fremden Daten ohne Loeschung,
      CASCADE beim Goal-Loeschen.
- [ ] Alle Tests laufen im Mock-Modus bzw. mit gepatchtem SDK -- deterministisch
      und kostenlos.
- [ ] Alle uebrigen Bestandstests bleiben unveraendert gruen.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Django 5.2, SQLite; eine neue Migration, keine Aenderung an bestehenden Tabellen.
- UI im bestehenden Bootstrap-5-Stil aus Feature 7; neue Routen fuegen sich in
  die Navigationsbereiche ein (Goal-Routen markieren "Goals").
- Bestehende Texte, auf die Tests pruefen, bleiben wortgleich.

**Out-of-Scope**

- Kein Bearbeiten von KI-Eintraegen.
- Kein Paginieren, Filtern oder Durchsuchen der Historie.
- Keine Kostenerfassung, kein Token-Zaehler, kein Rate-Limit pro Nutzer.
- Kein Export der Historie.
- Keine Uebernahme alter Session-Ergebnisse in die Datenbank (sie sind
  fluechtig und verfallen ohnehin).
- Keine Aenderung an Prompts, Modell oder Fehlerbehandlung des KI-Service.
