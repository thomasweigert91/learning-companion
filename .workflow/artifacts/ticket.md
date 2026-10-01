# Ticket: KI-Lernkarten-Generator mit interaktiver Abfrage

## 1. Problem / Ziel

Die KI-Unterstuetzung beschreibt bisher nur den Lernstand (Zusammenfassung) und
schlaegt naechste Schritte vor. Sie hilft aber nicht beim eigentlichen
**Festigen** des Gelernten. Wer ein Thema wiederholen will, muss sich Fragen
selbst ausdenken.

Dieses Ticket ergaenzt einen Lernkarten-Generator: Aus den Notizen der
Lernsitzungen und den Ressourcen eines Goals erzeugt die KI 3 bis 5
Frage-Antwort-Paare. Sie werden als Lernkarten gespeichert und auf der
Goal-Detailseite als Abfrage-Ansicht angezeigt: Die Frage ist sichtbar, die
Antwort wird erst auf Klick aufgedeckt. Gelernte Karten lassen sich markieren,
ueberfluessige loeschen.

Anders als Zusammenfassung und naechste Schritte liefert diese Aktion
**strukturierte Daten** statt Fliesstext. Deshalb nutzt der Service die
Structured Outputs der OpenAI-API mit einem JSON-Schema. Eine kaputte oder
unvollstaendige Antwort muss sauber abgefangen werden, statt halbe Karten zu
speichern oder einen 500er auszuloesen.

## 2. Akzeptanzkriterien

### Modell

- [ ] Neues Modell `Flashcard` mit `goal` (ForeignKey auf `Goal`,
      `on_delete=CASCADE`, `related_name="flashcards"`), `question`
      (TextField), `answer` (TextField), `is_mastered` (BooleanField,
      `default=False`) und `created_at` (`auto_now_add=True`).
- [ ] Sortierung fuer die Abfrage: noch nicht gelernte Karten zuerst, darin die
      neuesten zuerst (`is_mastered`, `-created_at`, `-pk`).
- [ ] Der Besitzer wird wie bei allen Kind-Modellen nur ueber `goal__user`
      aufgeloest, nicht redundant gespeichert.
- [ ] Migration `0005_flashcard` erzeugt und angewendet; rein additiv.
- [ ] Im Django-Admin registriert.

### Service (`core/services/ai_service.py`)

- [ ] Neue oeffentliche Funktion `generate_flashcards(goal)`; sie liefert eine
      Liste von `{"question": ..., "answer": ...}` und schreibt wie die
      bestehenden Funktionen **nichts** in die Datenbank.
- [ ] Der Prompt basiert auf demselben, auf das Goal begrenzten Kontext wie die
      anderen KI-Aktionen (Sitzungen mit Notizen, Ressourcen). Bereits
      vorhandene Fragen des Goals werden mitgegeben (gedeckelt), damit die KI
      keine Duplikate erzeugt.
- [ ] Der Aufruf nutzt das konfigurierte Modell (Standard `gpt-4o-mini`) mit
      `response_format` vom Typ `json_schema` und `strict: true`. Das Schema
      erzwingt ein Objekt mit einer Liste `cards`, deren Eintraege genau
      `question` und `answer` als Strings enthalten
      (`additionalProperties: false`).
- [ ] Die Anzahl 3 bis 5 wird **im Code** durchgesetzt, nicht dem Modell
      ueberlassen: mehr als 5 werden gekuerzt, weniger als 3 verwertbare
      Karten fuehren zu einem Fehler.
- [ ] Fehlerbehandlung -- jeder dieser Faelle endet in einer verstaendlichen
      `AIServiceError` und wird protokolliert, nie in einem 500er:
      kein gueltiges JSON, falsche Struktur (kein Objekt, keine Liste `cards`),
      Eintraege ohne oder mit leerem Text (werden verworfen), zu wenige
      verwertbare Karten, eine Ablehnung durch das Modell (`refusal`).
- [ ] Doppelte Fragen innerhalb einer Antwort und gegenueber vorhandenen Karten
      (Vergleich ohne Gross-/Kleinschreibung und Randleerzeichen) werden
      verworfen.
- [ ] Der Mock-Modus liefert deterministisch 3 Karten aus den echten Goal-Daten.

### Aktion und Verwaltung

- [ ] Button "Lernkarten generieren" in der KI-Card der Goal-Detailseite;
      die Aktion ist nur per POST ausloesbar (GET -> 405).
- [ ] Bei Erfolg werden die Karten gespeichert und angehaengt (bestehende
      Karten und ihr Lernstatus bleiben erhalten); Redirect auf `#lernkarten`
      mit Erfolgsmeldung, die im Abschnitt selbst erscheint.
- [ ] Bei einem Fehler wird nichts gespeichert; die Fehlermeldung erscheint
      ebenfalls im Abschnitt.
- [ ] Der Button erhaelt denselben Ladezustand wie die beiden bestehenden
      KI-Buttons (Spinner, alle KI-Buttons gesperrt), Ladetext
      "Erstelle Lernkarten...".
- [ ] Je Karte: "Als gelernt markieren" bzw. "Wieder lernen" (Umschalten von
      `is_mastered`) und "Loeschen" -- beide nur per POST.

### Abfrage-Ansicht

- [ ] Abschnitt "Lernkarten" (`id="lernkarten"`) als Bootstrap-Akkordeon: Die
      Frage ist die Kopfzeile, die Antwort wird erst beim Aufklappen sichtbar.
- [ ] Gelernte Karten tragen ein Badge "Gelernt" (Text, nicht nur Farbe).
- [ ] Fortschrittsanzeige "x von y gelernt" mit zugaenglichem Balken.
- [ ] Leerzustand mit Hinweis auf den Button.
- [ ] Die Karten werden mit einer festen Anzahl von Abfragen geladen,
      unabhaengig von ihrer Zahl.

### Isolation und Sicherheit

- [ ] Alle Routen erfordern Login. Fuer fremde Goals bzw. Karten liefern sie
      **404**, ohne etwas zu aendern; bei fremden Goals wird der Service gar
      nicht erst aufgerufen.
- [ ] Karten eines Goals erscheinen nie auf der Seite eines anderen Goals.
- [ ] KI-Text wird escaped ausgegeben.
- [ ] Wird ein Goal geloescht, verschwinden seine Karten (CASCADE); die
      Loesch-Bestaetigung nennt sie.

### Tests

- [ ] Service: Mock-Ergebnis, Schema-Parameter im SDK-Aufruf, gueltige
      Antwort, ungueltiges JSON, falsche Struktur, leere Felder, zu wenige und
      zu viele Karten, Duplikate, Refusal, Prompt nur mit eigenen Goal-Daten.
- [ ] Views: Speichern, Fehlerfall ohne Speichern, Umschalten, Loeschen,
      GET -> 405, Login-Pflicht, 404 ohne Aenderung bei fremden Daten,
      Service-Aufruf bei fremdem Goal ausgeschlossen.
- [ ] Anzeige: Akkordeon, Sortierung, Fortschritt, Leerzustand,
      Abfrage-Anzahl, keine Karten anderer Goals.
- [ ] Alle Tests deterministisch und ohne Netzwerk (Mock bzw. gepatchtes SDK);
      alle Bestandstests gruen.

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- `openai` SDK 1.x; Structured Outputs ueber `chat.completions.create` mit
  `response_format={"type": "json_schema", ...}`. Das JSON wird selbst
  geparst und validiert, damit jeder Fehlerfall explizit behandelt und
  testbar ist.
- `minItems`/`maxItems` werden bewusst **nicht** ins Schema geschrieben: Die
  Anzahl wird ohnehin im Code durchgesetzt, und ein im Strict-Modus nicht
  unterstuetztes Schluesselwort wuerde jede Anfrage mit einem Schemafehler
  scheitern lassen.
- Das Akkordeon nutzt Bootstraps eigene Collapse-Komponente; es kommt kein
  zusaetzliches JavaScript hinzu ausser der Erweiterung des bestehenden
  Ladezustands-Scripts.
- Meldungen, die in einem Abschnitt statt oben auf der Seite erscheinen,
  werden vereinheitlicht (KI-Verlauf und Lernkarten nutzen denselben
  Mechanismus).
- Bestehende Texte, auf die Tests pruefen, bleiben wortgleich.

**Out-of-Scope**

- Keine Wiederholungsplanung (Spaced Repetition), keine Faelligkeitsdaten.
- Kein Bearbeiten von Karten und kein manuelles Anlegen.
- Kein separater Vollbild-Quizmodus, keine Punkte oder Statistiken ueber das
  "x von y gelernt" hinaus.
- Keine Lernkarten im Dashboard.
- Keine Aenderung an Zusammenfassung, naechsten Schritten oder deren Prompts.
