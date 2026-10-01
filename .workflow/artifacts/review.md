# Code Review: Django-Projekt "learning_companion" mit App "core", Auth & Profil

**Status: APPROVED**

Geprüft gegen `.workflow/artifacts/ticket.md` und `.workflow/artifacts/plan.md`.
Stand: Django 5.2.17, Python 3.12.10, 17 Tests, `validate_code.ps1` grün.

---

## 1. Abdeckung der Akzeptanzkriterien

| # | Akzeptanzkriterium | Nachweis | Erfüllt |
|---|---|---|---|
| 1 | `manage.py check` Exit-Code 0 | Kommando-Exit 0; Hook `validate_code.ps1` | ja |
| 2 | Projekt `learning_companion`, App `core` in `INSTALLED_APPS` | `learning_companion/settings.py:48` | ja |
| 3 | `migrate` fehlerfrei, Migration eingecheckt | 19 Migrationen angewandt; `core/migrations/0001_initial.py` | ja |
| 4 | `Profile` mit `user`/`name`/`cohort`/`focus_areas` | `core/models.py:30-46` | ja |
| 5 | Profil automatisch bei Registrierung, genau eines | `core/signals.py`; `test_profile_created_automatically_on_user_creation` | ja |
| 6 | `__str__` menschenlesbar | `core/models.py:52`; `test_profile_str_is_human_readable` | ja |
| 7 | Registrierung: 302 bei gültig, 200 + Fehler bei ungültig, kein User | `test_register_creates_user_and_redirects`, `test_register_with_duplicate_username_fails`, `test_register_with_password_mismatch_fails` | ja |
| 8 | Login: Session bei korrekt, 200 + Fehler bei falsch | `test_login_success`, `test_login_invalid_credentials` | ja |
| 9 | Logout beendet Session, danach Redirect auf Login | `test_logout_ends_session` | ja |
| 10 | Passwörter nur gehasht | `test_password_is_hashed` (prüft `pbkdf2_`-Präfix und `check_password`) | ja |
| 11 | Eigenes Profil: 200 inkl. Name, Cohort, Focus Areas | `test_profile_detail_shows_own_data` | ja |
| 12 | Eigenes Profil bearbeitbar, Werte in der DB | `test_profile_update_persists` | ja |
| 13 | Anonymer Zugriff → 302 auf Login | `test_anonymous_redirected_from_profile_detail`, `..._from_profile_edit` | ja |
| 14 | Fremdes Profil → 404/403, weder lesbar noch änderbar | `test_user_cannot_access_foreign_profile_detail`, `test_user_cannot_edit_foreign_profile` | ja |
| 15 | Tests decken Registrierung, Login/Logout, Profilerstellung, eigener/fremder Zugriff ab | `core/tests/` (3 Module, 17 Tests) | ja |
| 16 | `manage.py test` Exit-Code 0 | 17/17 grün in 4,9 s | ja |

**16 von 16 Kriterien erfüllt.**

## 2. Sicherheit

**Auth-Bypass — geprüft, kein Befund.**
`OwnProfileMixin.get_queryset()` (`core/views.py:44`) schränkt grundsätzlich auf `Profile.objects.filter(user=self.request.user)` ein. Die Hauptrouten `/profile/` und `/profile/edit/` tragen keinen PK, sind also gar nicht fremdadressierbar; die PK-Routen laufen über das gefilterte Queryset und liefern für ein fremdes Profil 404. `LoginRequiredMixin` steht an erster Stelle der MRO, greift also vor jeder Objektauflösung.

Positiv hervorzuheben: `test_user_cannot_edit_foreign_profile` prüft nach dem abgewiesenen POST zusätzlich per `refresh_from_db()`, dass B's Daten unverändert sind. Damit ist belegt, dass nicht nur die Anzeige, sondern auch der Schreibpfad blockiert ist — der Fall, den eine reine Statuscode-Prüfung übersehen würde.

**SQL-Injection — keine Angriffsfläche.** Ausschließlich ORM-Zugriffe, kein `raw()`, kein `extra()`, keine String-Interpolation in Queries.

**CSRF.** Alle vier schreibenden Formulare (Login, Registrierung, Profil-Edit, Logout) tragen `{% csrf_token %}`; `CsrfViewMiddleware` ist aktiv. Logout ist korrekt als POST-Formular umgesetzt, nicht als Link.

**Passwörter.** Hashing und Validierung kommen unverändert aus `django.contrib.auth`; die vier Standard-Validatoren sind aktiv. Keine Eigenimplementierung.

**Konfiguration.** `SECRET_KEY`, `DEBUG` und `ALLOWED_HOSTS` sind über Umgebungsvariablen steuerbar; `.env` ist in `.gitignore`.

## 3. Hinweise ohne Blocker-Charakter

Keiner dieser Punkte verletzt ein Akzeptanzkriterium; sie sind für spätere Iterationen notiert.

1. **Dev-Fallback für `SECRET_KEY`** (`settings.py:16`): Ist `DJANGO_SECRET_KEY` nicht gesetzt, startet die App mit einem im Repo stehenden Schlüssel, ebenso läuft `DEBUG` per Default auf `True`. Für die lokale Entwicklung gewollt und durch "kein Deployment" im Ticket als Out-of-Scope gedeckt — vor einem echten Deployment aber zwingend zu härten (Fail-Fast statt Fallback).
2. **Kein Brute-Force-Schutz am Login.** Unbegrenzte Loginversuche; Rate-Limiting ist im Ticket nicht gefordert.
3. **`email` ist nicht `unique`.** Entspricht dem Django-Standard-User und war nicht gefordert; mehrere Konten mit derselben Adresse sind damit möglich.
4. **Keine `clean`-Normalisierung auf `Tag.name`.** `"Python"` und `"python "` wären zwei Tags. Tags werden derzeit nur über das Admin gepflegt, daher unkritisch.

## 4. Formatierung und tote Code-Pfade

Imports sortiert und vollständig genutzt, keine auskommentierten Reste, konsistente Namensgebung, Docstrings an allen nicht-trivialen Stellen. `manage.py check` meldet 0 Issues.

Ein toter Pfad wurde **während der Implementierung gefunden und behoben**: `ProfileUpdateView` hatte zunächst ein explizites `success_url`, wodurch `Profile.get_absolute_url()` nie aufgerufen wurde. Das `success_url` wurde entfernt, das Redirect-Ziel kommt jetzt aus `get_absolute_url()` — eine Quelle statt zwei. Tests danach erneut grün.

## 5. Abweichungen vom Plan

| Abweichung | Begründung |
|---|---|
| `core/templates/registration/logged_out.html` **nicht** angelegt | Der Plan sah zugleich `LOGOUT_REDIRECT_URL = "/"` vor. Beides zusammen schließt sich aus: bei gesetztem Redirect rendert `LogoutView` das Template nie. Statt eine unerreichbare Datei anzulegen, wurde sie weggelassen. |
| Zwei zusätzliche Routen `profile_detail_pk` / `profile_edit_pk` | Im Plan unter Schritt 4 vorgesehen, hier nur zur Klarstellung: Sie existieren, damit das Ticket-Kriterium "fremde Profil-URL → 404" überhaupt testbar ist. Ohne PK-Route gäbe es keine URL, die man angreifen könnte. |
| 17 statt der 15 geplanten Tests | `test_own_pk_route_still_works` ergänzt (die PK-Route muss für das *eigene* Profil weiterhin 200 liefern — sonst wäre der 404-Test auch durch eine kaputte Route erfüllbar), plus Aufteilung eines Login-Tests. |
| Migration handgeschrieben statt per `makemigrations` erzeugt | Zum Zeitpunkt der Erstellung war kein Python installiert. Deckungsgleichheit anschließend verifiziert: `makemigrations --check --dry-run` meldet "No changes detected". |
| Python 3.12.10 und `.venv/` neu angelegt | Auf dem Rechner war kein Python vorhanden (nur der Store-Alias-Stub). Installation nach Rückfrage und Freigabe, benutzerbezogen via winget. |

## 6. Fazit

Alle 16 Akzeptanzkriterien sind erfüllt und durch Tests oder Kommando-Exit-Codes belegt. Die Zugriffskontrolle ist strukturell gelöst statt nachträglich geprüft, was die Klasse von Fehlern ausschließt, bei der eine vergessene Prüfung ein fremdes Profil freilegt. Keine Sicherheitsbefunde, keine toten Pfade, keine offenen Nachbesserungen.

**Status: APPROVED**
