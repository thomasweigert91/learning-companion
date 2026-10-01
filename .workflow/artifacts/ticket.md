# Ticket: AI-powered summary and next steps — OpenAI-Integration für Fortschritt und Lernempfehlungen

## 1. Problem / Ziel

Nutzer erfassen Lernziele, dokumentieren Lernsitzungen und hängen Ressourcen an. Was daraus entsteht, ist eine wachsende Datenspur, die niemand auswertet: Wer zwölf Sessions an einem Ziel hat, sieht eine Liste — keine Einordnung, wo er steht und was als Nächstes sinnvoll wäre.

Dieses Ticket bindet die OpenAI-API an und ergänzt zwei Aktionen auf der Goal-Detailseite:

1. **Generate summary** — sammelt die jüngsten `LearningSession`s und `Resource`s des Goals, schickt sie an `gpt-4o-mini` und zeigt eine strukturierte Fortschrittszusammenfassung.
2. **Suggest next steps** — schickt das Goal samt bisherigen Sessions an die API und liefert 2–3 konkrete nächste Lernschritte als Liste.

Drei Randbedingungen sind so wichtig wie die Features selbst:

- Der **API-Key darf nirgends im Code oder Repository stehen**, sondern wird ausschließlich über Umgebungsvariablen geladen.
- Die Testsuite darf **keine externen API-Calls** auslösen und muss ohne API-Key vollständig durchlaufen. Dasselbe gilt für die lokale Entwicklung ohne Key.
- **Netzwerkfehler, Timeouts und Rate-Limits dürfen die Anwendung nicht zum Absturz bringen**, sondern erzeugen eine verständliche Meldung über das Django-Messages-Framework.

Das Scoping bleibt unverändert streng: Beide Aktionen arbeiten ausschließlich auf eigenen Goals.

## 2. Akzeptanzkriterien

**Konfiguration und Schlüsselverwaltung**

- [ ] Das Paket `openai` ist in `requirements.txt` mit Versionsgrenze eingetragen und im `.venv` installiert.
- [ ] `OPENAI_API_KEY` wird ausschließlich über `os.environ` gelesen; eine Suche über das gesamte Repository (ohne `.venv/`) nach einem Schlüssel-Literal (`sk-`) liefert **keinen** Treffer.
- [ ] `.env.example` dokumentiert `OPENAI_API_KEY`, `OPENAI_MODEL` und den Mock-Schalter mit unverfänglichen Platzhaltern; `.env` bleibt über `.gitignore` ausgeschlossen.
- [ ] Das verwendete Modell ist über die Einstellung `OPENAI_MODEL` konfigurierbar und hat den Default `gpt-4o-mini`.
- [ ] Ein fehlender `OPENAI_API_KEY` führt **nicht** zu einem Fehler beim Start: `python manage.py check` endet auch ohne gesetzten Key mit Exit-Code 0.

**Service-Layer**

- [ ] Die gesamte OpenAI-Anbindung liegt in einem Service-Modul; weder Views noch Models noch Templates importieren das `openai`-SDK direkt.
- [ ] Der Service stellt zwei Funktionen bereit: eine für die Fortschrittszusammenfassung und eine für die nächsten Lernschritte. Beide nehmen ein `Goal` entgegen und liefern ein Ergebnis zurück, ohne die Datenbank zu verändern.
- [ ] Die Zusammenfassung erhält die jüngsten Lernsitzungen (Datum, Dauer, Notizen) und die Ressourcen (Titel, Typ) des Goals als Kontext; die Anzahl der übergebenen Sitzungen ist begrenzt und nicht unbeschränkt.
- [ ] Die Funktion für die nächsten Schritte liefert eine **Liste** von 2 bis 3 Einträgen zurück, nicht einen Fließtext-Block.
- [ ] An die API werden ausschließlich Daten des übergebenen Goals übermittelt; Daten anderer Nutzer sind im Prompt nicht enthalten (belegt durch einen Test, der den Prompt-Inhalt prüft).

**Mock-Modus**

- [ ] Es existiert ein Mock-Modus, der deterministische Ergebnisse liefert, ohne das Netzwerk zu berühren.
- [ ] Der Mock-Modus ist aktiv, wenn er explizit eingeschaltet ist **oder** kein `OPENAI_API_KEY` vorliegt. Damit läuft die Anwendung lokal ohne Key benutzbar weiter.
- [ ] Während `python manage.py test` findet **kein** externer API-Call statt. Nachweis: ein Test, der das SDK so ersetzt, dass jeder echte Aufruf den Test scheitern lässt, und danach beide Aktionen ausführt.
- [ ] Die vollständige Testsuite läuft auch dann durch, wenn `OPENAI_API_KEY` in der Umgebung **gesetzt** ist — der Testlauf erzwingt den Mock-Modus unabhängig von der Umgebung.

**Aktionen auf der Goal-Detailseite**

- [ ] Die Goal-Detailseite enthält zwei POST-Formulare mit `{% csrf_token %}`: eines für die Zusammenfassung, eines für die nächsten Schritte. Beide lösen per GET keine Aktion aus.
- [ ] Ein POST auf die Zusammenfassungs-Aktion liefert einen Redirect (302) zurück auf die Goal-Detailseite; das Ergebnis ist dort anschließend als Text sichtbar.
- [ ] Ein POST auf die Next-Steps-Aktion liefert einen Redirect (302); das Ergebnis ist anschließend als Liste mit 2 bis 3 Einträgen sichtbar.
- [ ] Vor der ersten Nutzung erscheint auf der Detailseite kein leerer Ergebnisbereich, sondern die Aktionen stehen ohne Platzhalter-Rumpf.
- [ ] Die generierten Ergebnisse werden nicht dauerhaft in der Datenbank gespeichert; es ist keine neue Migration für Ergebnistexte nötig.

**Fehlerbehandlung**

- [ ] Django-Messages werden im Basis-Template ausgegeben (bislang nicht der Fall) und erscheinen damit auf allen Seiten.
- [ ] Ein Timeout der API führt zu Status 302 zurück auf die Detailseite und einer Fehlermeldung über das Messages-Framework; die Seite bleibt bedienbar und es entsteht kein 500er.
- [ ] Ein Rate-Limit-Fehler der API wird ebenso abgefangen und erzeugt eine eigene, verständliche Meldung.
- [ ] Ein unerwarteter Fehler aus dem SDK (beliebige Exception) wird ebenfalls abgefangen und führt nicht zu einem 500er.
- [ ] Die Fehlermeldungen enthalten **keine** technischen Interna wie API-Key, Stacktrace oder rohe SDK-Fehlertexte.

**Scoping und Zugriffskontrolle**

- [ ] Beide Aktionen leiten einen nicht eingeloggten Aufruf mit Status 302 auf die Login-Seite um.
- [ ] Ein POST von Nutzer A auf eine der beiden Aktionen für ein **fremdes** Goal (Nutzer B) liefert Status 404; es wird kein API-Aufruf ausgelöst und kein Ergebnis erzeugt.
- [ ] Zur Gegenprobe ist belegt, dass beide Aktionen am eigenen Goal funktionieren.

**Tests und Regression**

- [ ] Automatisierte Tests decken ab: Service im Mock-Modus, Prompt-Inhalt (nur eigene Daten, Begrenzung der Sitzungszahl), beide Views inklusive Anzeige der Ergebnisse, alle drei Fehlerpfade (Timeout, Rate-Limit, unerwartete Exception) sowie das Scoping.
- [ ] Die bestehenden 90 Tests aus Feature 1 bis 3 laufen unverändert weiter durch.
- [ ] `python manage.py check` und `python manage.py test` enden mit Exit-Code 0.
- [ ] `python manage.py makemigrations --check --dry-run` meldet keine ausstehenden Änderungen (dieses Feature bringt kein neues Modell mit).

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Bestehender Stack unverändert: Python 3.12, Django 5.2, SQLite, serverseitig gerenderte Templates. Einzige neue Abhängigkeit: `openai`.
- Modell: `gpt-4o-mini` als Default, über die Einstellung `OPENAI_MODEL` austauschbar.
- Die Anbindung liegt in einem Service-Layer unter `core/services/`; Views rufen ausschließlich diesen Service auf. Damit bleibt das SDK an einer Stelle austauschbar und die Views sind ohne Netzwerk testbar.
- Der Service wirft eine eigene Exception-Klasse. SDK-spezifische Fehlertypen werden dort in diese Klasse übersetzt und erreichen die Views nicht — die Views kennen das SDK nicht.
- Die Ergebnisse sind flüchtig und werden in der Session des Nutzers gehalten, nicht in der Datenbank. Begründung: generierte Texte sind Momentaufnahmen, kein Stammdatum; so entfällt eine Migration und es entstehen keine veralteten Zusammenfassungen im Datenbestand.
- Scoping wie in den Vorfeatures: Das Goal wird über ein auf `request.user` gescoptes Queryset aufgelöst, ein fremder PK ergibt 404 **bevor** ein API-Aufruf stattfindet.
- Timeout und Wiederholungsverhalten werden explizit gesetzt, damit ein hängender API-Aufruf keinen Request-Thread blockiert.
- Die Testsuite erzwingt den Mock-Modus unabhängig von der Umgebung des Entwicklers.

**Out-of-Scope**

- Kein Streaming der Antworten, kein Token-Zähler, keine Kostenanzeige.
- Keine Speicherung oder Historie generierter Zusammenfassungen; kein Vergleich über die Zeit.
- Keine Hintergrundverarbeitung (kein Celery, keine Queue) — die Aufrufe laufen synchron im Request.
- Kein Caching der Antworten und keine Deduplizierung gleicher Anfragen.
- Keine Nutzung weiterer OpenAI-Funktionen (Embeddings, Function Calling, Assistants, Vision).
- Keine KI-Funktionen an anderer Stelle (Profil, Sessions-Liste, Ressourcen).
- Kein Rate-Limiting oder Kontingent pro Nutzer auf Anwendungsseite.
- Keine Mehrsprachigkeit der generierten Texte über die vorgegebene Sprache hinaus.
- Kein individuelles UI-Design; Styling bleibt minimal.

**Ausdrücklicher Hinweis zur Verifizierbarkeit**

In dieser Umgebung ist **kein `OPENAI_API_KEY` vorhanden**. Der echte API-Pfad ist damit nicht end-to-end verifizierbar. Die Abnahme erfolgt über den Mock-Modus und über Tests, die das SDK gezielt durch Fehler werfende Doubles ersetzen. Die Korrektheit des Aufruf-Codes gegen die echte API bleibt bis zu einem Lauf mit gültigem Schlüssel ungeprüft; dieser Vorbehalt ist im Review festzuhalten.
