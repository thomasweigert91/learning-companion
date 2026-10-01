# Ticket: Django-Projekt "learning_companion" mit App "core", Basis-Authentifizierung und Nutzerprofil

## 1. Problem / Ziel

Es existiert noch keine lauffähige Codebasis. Als Grundlage für alle weiteren Features wird ein Django-Projekt `learning_companion` mit der App `core` benötigt.

Die Basis muss zwei Dinge liefern:

1. **Authentifizierung** – Nutzer können sich registrieren, einloggen und ausloggen.
2. **Profil** – Zu jedem Nutzer existiert genau ein Profil mit Name, Cohort und Focus Areas (Tags). Nutzer dürfen ausschließlich ihr eigenes Profil sehen und bearbeiten.

Ziel ist ein deploybares Grundgerüst, auf dem Lernfunktionen aufbauen können, mit einer von Beginn an korrekt durchgesetzten Zugriffskontrolle (keine fremden Profile sichtbar oder änderbar).

## 2. Akzeptanzkriterien

**Projekt-Setup**

- [ ] `python manage.py check` läuft im Projektverzeichnis fehlerfrei durch (Exit-Code 0).
- [ ] Das Django-Projekt heißt `learning_companion`, die App heißt `core` und ist in `INSTALLED_APPS` eingetragen.
- [ ] `python manage.py migrate` erzeugt alle Tabellen fehlerfrei; für `core` existiert mindestens eine eingecheckte Migrationsdatei.

**Profil-Modell**

- [ ] Es existiert ein Modell `Profile` mit den Feldern: `user` (OneToOneField auf `settings.AUTH_USER_MODEL`, `on_delete=CASCADE`), `name` (CharField), `cohort` (CharField) und `focus_areas` (Tags, mehrere Werte pro Profil möglich).
- [ ] Beim Registrieren eines neuen Nutzers wird automatisch genau ein zugehöriges `Profile` angelegt (Test: nach Registrierung gilt `Profile.objects.filter(user=neuer_user).count() == 1`).
- [ ] `Profile.__str__()` liefert einen menschenlesbaren Wert (z. B. Username bzw. Name).

**Authentifizierung**

- [ ] Registrierung unter `/accounts/register/`: Ein POST mit gültigen Daten legt einen neuen User an und leitet per Redirect (Status 302) weiter; bei ungültigen Daten (z. B. Username bereits vergeben, Passwörter stimmen nicht überein) wird das Formular mit Status 200 und sichtbarer Fehlermeldung erneut angezeigt und **kein** User angelegt.
- [ ] Login unter `/accounts/login/`: Korrekte Credentials erzeugen eine authentifizierte Session (Redirect 302); falsche Credentials führen zu Status 200 mit Fehlermeldung und **keiner** Session.
- [ ] Logout unter `/accounts/logout/` beendet die Session; ein anschließender Aufruf einer geschützten Seite leitet auf die Login-Seite um.
- [ ] Passwörter werden ausschließlich gehasht gespeichert (Django-Default-Hasher); im Klartext ist kein Passwort in der Datenbank auffindbar.

**Zugriffskontrolle (eigenes Profil)**

- [ ] Eine Profil-Detailansicht zeigt einem eingeloggten Nutzer sein eigenes Profil mit Status 200 inkl. Name, Cohort und Focus Areas.
- [ ] Eine Profil-Bearbeitungsansicht erlaubt dem eingeloggten Nutzer, `name`, `cohort` und `focus_areas` des **eigenen** Profils zu ändern; nach dem Speichern sind die Werte in der Datenbank aktualisiert.
- [ ] Ein nicht eingeloggter Aufruf von Profil-Detail oder Profil-Bearbeitung leitet mit Status 302 auf die Login-Seite um.
- [ ] Ein eingeloggter Nutzer A, der gezielt die Profil-Detail- oder Bearbeitungs-URL eines fremden Profils (Nutzer B) aufruft, erhält Status 404 (oder 403) und kann die Daten von B weder sehen noch verändern — belegt durch einen automatisierten Test.

**Tests**

- [ ] Automatisierte Tests in `core/tests.py` (oder `core/tests/`) decken ab: Registrierung (Erfolg + Fehlerfall), Login/Logout, automatische Profilerstellung, Zugriff auf eigenes Profil sowie verweigerter Zugriff auf fremdes Profil.
- [ ] `python manage.py test` läuft vollständig grün durch (Exit-Code 0).

## 3. Technische Rahmenbedingungen & Out-of-Scope

**Rahmenbedingungen**

- Python 3.11+, Django 5.x (LTS-nah), Standard-ORM.
- Datenbank: SQLite für die lokale Entwicklung (`db.sqlite3`); die Konfiguration bleibt austauschbar.
- Es wird das Django-Standard-`User`-Modell verwendet; das Profil wird per `OneToOneField` angebunden (kein Custom User Model).
- Authentifizierung baut auf `django.contrib.auth` auf (`LoginView`, `LogoutView`, `UserCreationForm`); keine Eigenimplementierung von Login/Passwort-Logik.
- `focus_areas` wird als Tag-Liste modelliert — Umsetzung über eine eigene `Tag`-Model-Klasse mit `ManyToManyField` (bevorzugt, DB-unabhängig) oder eine äquivalente Tag-Lösung; die konkrete Wahl trifft die technische Planung.
- Zugriffsschutz über `LoginRequiredMixin` / `@login_required`; die Objektauswahl erfolgt grundsätzlich über `request.user` (kein Profil-Lookup allein über eine URL-PK).
- Templates: einfache, serverseitig gerenderte Django-Templates; `SECRET_KEY` und `DEBUG` werden über Umgebungsvariablen konfigurierbar gehalten.
- `requirements.txt` und eine `.gitignore` (mind. `db.sqlite3`, `__pycache__/`, `.env`) gehören zum Lieferumfang.

**Out-of-Scope**

- Keine REST-API (kein Django REST Framework), keine SPA, kein JavaScript-Frontend.
- Kein Passwort-Reset per E-Mail, keine E-Mail-Verifizierung, kein Social Login / OAuth, keine 2FA.
- Keine Rollen- oder Rechteverwaltung über das eigene Profil hinaus (kein Admin-Zugriff auf fremde Profile als Feature).
- Keine Lern-/Companion-Fachlogik (Kurse, Fortschritt, Empfehlungen) — nur das Grundgerüst.
- Kein CI/CD, kein Docker, kein Deployment auf einen Server, kein produktives Logging/Monitoring.
- Kein individuelles UI-Design / CSS-Framework; Styling ist minimal.
