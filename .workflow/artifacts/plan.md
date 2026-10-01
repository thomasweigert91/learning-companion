# Implementierungs-Plan: Django-Projekt "learning_companion" mit App "core", Auth & Profil

## 1. Betroffene Dateien

**Projekt-Wurzel**

- Neu: `manage.py`
- Neu: `requirements.txt`
- Neu: `.gitignore`
- Neu: `.env.example`

**Projekt-Package `learning_companion/`**

- Neu: `learning_companion/__init__.py`
- Neu: `learning_companion/settings.py`
- Neu: `learning_companion/urls.py`
- Neu: `learning_companion/wsgi.py`
- Neu: `learning_companion/asgi.py`

**App `core/`**

- Neu: `core/__init__.py`
- Neu: `core/apps.py`
- Neu: `core/models.py`
- Neu: `core/forms.py`
- Neu: `core/views.py`
- Neu: `core/urls.py`
- Neu: `core/signals.py`
- Neu: `core/admin.py`
- Neu: `core/migrations/__init__.py`
- Neu: `core/migrations/0001_initial.py` (per `makemigrations` erzeugt, eingecheckt)

**Templates**

- Neu: `core/templates/base.html`
- Neu: `core/templates/core/home.html`
- Neu: `core/templates/core/profile_detail.html`
- Neu: `core/templates/core/profile_form.html`
- Neu: `core/templates/registration/login.html`
- Neu: `core/templates/registration/register.html`
- Neu: `core/templates/registration/logged_out.html`

**Tests**

- Neu: `core/tests/__init__.py`
- Neu: `core/tests/test_auth.py`
- Neu: `core/tests/test_profile.py`
- Neu: `core/tests/test_access_control.py`

**Nicht zu ändern:** alles unterhalb `.workflow/` (Workflow-Infrastruktur, kein Produktivcode).

## 2. Datenmodelle & Migrationen

### Modelle (`core/models.py`)

**`Tag`** — normalisierte Focus Area, DB-unabhängig (kein `ArrayField`, damit SQLite funktioniert):

| Feld | Typ | Optionen |
| --- | --- | --- |
| `name` | `CharField` | `max_length=50`, `unique=True` |
| `slug` | `SlugField` | `max_length=50`, `unique=True`, in `save()` aus `name` abgeleitet |

- `Meta.ordering = ["name"]`
- `__str__` → `self.name`

**`Profile`** — 1:1 zum Django-Standard-User:

| Feld | Typ | Optionen |
| --- | --- | --- |
| `user` | `OneToOneField` | `settings.AUTH_USER_MODEL`, `on_delete=models.CASCADE`, `related_name="profile"` |
| `name` | `CharField` | `max_length=150`, `blank=True` |
| `cohort` | `CharField` | `max_length=100`, `blank=True` |
| `focus_areas` | `ManyToManyField` | `Tag`, `blank=True`, `related_name="profiles"` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

- `__str__` → `self.name or self.user.get_username()` (menschenlesbar, AK erfüllt)
- `get_absolute_url()` → `reverse("core:profile_detail")`

### Automatische Profilerstellung (`core/signals.py`)

- `post_save`-Receiver auf `settings.AUTH_USER_MODEL`: bei `created=True` → `Profile.objects.get_or_create(user=instance)`.
- `get_or_create` statt `create`, damit Fixtures oder mehrfaches Speichern keine `IntegrityError` auslösen.
- Registrierung in `core/apps.py` → `CoreConfig.ready()` mit `import core.signals`. Kein Import der Models auf Modulebene (vermeidet `AppRegistryNotReady`).

### Migrationen

- Ein Lauf `python manage.py makemigrations core` erzeugt `0001_initial.py` (Tag, Profile, M2M-Zwischentabelle). Die Datei wird eingecheckt.
- Danach `python manage.py migrate` — inkl. `auth`, `contenttypes`, `sessions`, `admin`.
- Keine Datenmigration nötig (Greenfield, keine Bestandsdaten).

### Settings-Eckpunkte (`learning_companion/settings.py`)

- `INSTALLED_APPS`: Django-Defaults + `"core"`.
- `SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "<dev-fallback>")`, `DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"`, `ALLOWED_HOSTS` aus Env (kommasepariert).
- `TEMPLATES[0]["APP_DIRS"] = True` — Templates liegen in `core/templates/`, `DIRS` bleibt leer.
- `LOGIN_URL = "/accounts/login/"`, `LOGIN_REDIRECT_URL = "/profile/"`, `LOGOUT_REDIRECT_URL = "/"`.
- `AUTH_PASSWORD_VALIDATORS`: Django-Defaults aktiv; Hashing über den Default-`PBKDF2PasswordHasher`.
- `LANGUAGE_CODE = "de-de"`, `TIME_ZONE = "Europe/Berlin"`, `USE_TZ = True`.
- `DATABASES`: SQLite auf `BASE_DIR / "db.sqlite3"`, gekapselt, damit später austauschbar.

## 3. Schrittweise Umsetzung

- [ ] **Schritt 1: Projekt-Setup & Gerüst** — `requirements.txt` (`Django>=5.0,<6.0`) anlegen; `django-admin startproject learning_companion .` und `python manage.py startapp core` ausführen; `"core"` in `INSTALLED_APPS` eintragen; `.gitignore` (`db.sqlite3`, `__pycache__/`, `*.pyc`, `.env`, `.venv/`) und `.env.example` schreiben; Settings auf Env-Variablen für `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` umstellen; `LOGIN_URL`/`LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL`, Sprache und Zeitzone setzen. Abnahme: `python manage.py check` endet mit Exit-Code 0.

- [ ] **Schritt 2: Models, Signal & Migration** — `Tag` und `Profile` in `core/models.py` implementieren (inkl. `__str__`, `get_absolute_url`, Slug-Ableitung); `core/signals.py` mit dem `post_save`-Receiver; `CoreConfig.ready()` in `core/apps.py` um `import core.signals` erweitern; `core/admin.py` registriert `Tag` und `Profile`. Danach `python manage.py makemigrations core` und `python manage.py migrate`. Abnahme: `0001_initial.py` existiert, `migrate` läuft fehlerfrei.

- [ ] **Schritt 3: Authentifizierung (Register / Login / Logout)** — `core/forms.py`: `RegistrationForm(UserCreationForm)` mit den Feldern `username`, `email` (optional), `password1`, `password2`; `core/views.py`: `RegisterView(CreateView)` mit `form_class=RegistrationForm`, `success_url = reverse_lazy("core:profile_detail")` und automatischem Login des neuen Users in `form_valid()`; `core/urls.py` mit `app_name = "core"` und den Routen `/accounts/register/`, `/accounts/login/` (`auth_views.LoginView`) und `/accounts/logout/` (`auth_views.LogoutView`); Einbindung in `learning_companion/urls.py` via `include("core.urls")`. Hinweis: `LogoutView` erfordert in Django 5 einen POST — das Logout-Element wird deshalb als POST-Formular mit CSRF-Token gerendert, Tests nutzen `self.client.post`.

- [ ] **Schritt 4: Profil-Views mit Zugriffskontrolle** — `core/forms.py`: `ProfileForm(ModelForm)` auf `Profile` mit `fields = ["name", "cohort", "focus_areas"]` und `CheckboxSelectMultiple` für `focus_areas`; `core/views.py`: `ProfileDetailView(LoginRequiredMixin, DetailView)` und `ProfileUpdateView(LoginRequiredMixin, UpdateView)`, beide mit `get_object()` → `self.request.user.profile` (**kein** `pk`/`slug` aus der URL). Die Routen `/profile/` und `/profile/edit/` tragen keinen PK-Parameter — damit existiert gar keine URL, über die ein fremdes Profil adressierbar wäre; der Schutz ist strukturell statt nur geprüft. Zusätzlich die bewusst abgesicherte Route `/profile/<int:pk>/`: `get_queryset()` filtert auf `Profile.objects.filter(user=self.request.user)`, ein fremder PK liefert damit automatisch 404. `HomeView(TemplateView)` auf `/` als öffentlicher Einstieg.

- [ ] **Schritt 5: Templates** — `base.html` mit Navigation (eingeloggt: Profil-Link und Logout-POST-Formular; ausgeloggt: Login und Registrierung) und `{% block content %}`; `core/home.html`; `core/profile_detail.html` zeigt `name`, `cohort` und die `focus_areas` als Liste; `core/profile_form.html`, `registration/login.html` und `registration/register.html` rendern die Formulare inklusive `{% csrf_token %}` und sichtbarer Fehlerausgabe (Pflicht für die Akzeptanzkriterien zu Fehlermeldungen); `registration/logged_out.html`. Styling minimal, kein CSS-Framework.

- [ ] **Schritt 6: Tests schreiben** — `core/tests/` als Package anlegen (die von `startapp` erzeugte `core/tests.py` wird dafür entfernt) mit den drei Testmodulen gemäß Abschnitt 4.

- [ ] **Schritt 7: Gesamtvalidierung** — `python manage.py check`, `python manage.py test` und abschließend `.\.workflow\hooks\validate_code.ps1` ausführen; alles muss mit Exit-Code 0 enden.

## 4. Validierung & Test-Strategie

### `core/tests/test_auth.py`

- `test_register_creates_user_and_redirects` — POST auf `/accounts/register/` mit gültigen Daten → Status 302 und `User.objects.filter(username=...).exists()` ist `True`.
- `test_register_with_duplicate_username_fails` — POST mit bereits vergebenem Username → Status 200, `response.context["form"].errors` nicht leer, User-Anzahl unverändert.
- `test_register_with_password_mismatch_fails` — abweichende `password1`/`password2` → Status 200, Formularfehler, kein neuer User.
- `test_password_is_hashed` — nach der Registrierung gilt `user.password != "<klartext>"` und `user.check_password("<klartext>")` ist `True`.
- `test_login_success` / `test_login_invalid_credentials` — korrekte Credentials → 302 und `response.wsgi_request.user.is_authenticated`; falsche → 200 mit Formularfehler und anonymem User.
- `test_logout_ends_session` — POST auf `/accounts/logout/`, danach GET auf `/profile/` → 302 auf die Login-URL.

### `core/tests/test_profile.py`

- `test_profile_created_automatically_on_user_creation` — nach der Registrierung gilt `Profile.objects.filter(user=user).count() == 1`.
- `test_profile_str_is_human_readable` — `str(profile)` enthält Username bzw. gesetzten Namen, nicht `"Profile object (1)"`.
- `test_profile_detail_shows_own_data` — eingeloggt, GET `/profile/` → 200, Response enthält `name`, `cohort` und die Tag-Namen.
- `test_profile_update_persists` — POST auf `/profile/edit/` mit neuen Werten inkl. Tag-IDs → Redirect; nach `profile.refresh_from_db()` entsprechen `name`, `cohort` und `focus_areas` den gesendeten Werten.

### `core/tests/test_access_control.py`

- `test_anonymous_redirected_from_profile_detail` und `test_anonymous_redirected_from_profile_edit` — GET ohne Login → 302 mit `/accounts/login/` im `Location`-Header (`assertRedirects`).
- `test_user_cannot_access_foreign_profile_detail` — User A eingeloggt, GET `/profile/<pk_von_B>/` → Status 404 (bzw. 403); die Response enthält keine Daten von B.
- `test_user_cannot_edit_foreign_profile` — User A eingeloggt, POST auf die Edit-URL mit B's PK → 404/403, und nach `profile_b.refresh_from_db()` sind B's Werte unverändert (prüft, dass nicht nur die Anzeige, sondern auch der Schreibpfad blockiert ist).
- `test_profile_edit_updates_only_own_profile` — nach einem gültigen Edit durch A sind B's Felder unverändert.

### Testdaten

- Setup über `User.objects.create_user()` plus das automatisch erzeugte Profil; `Tag`-Instanzen werden je Testklasse in `setUpTestData` angelegt.
- Keine Fixture-Dateien, keine externen Abhängigkeiten; die Tests laufen gegen die Django-Test-Datenbank (SQLite).

### Auszuführende Kommandos

```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
.\.workflow\hooks\validate_code.ps1
```

### Definition of Done

Alle vier Kommandos enden mit Exit-Code 0, `core/migrations/0001_initial.py` ist eingecheckt, und jedes Akzeptanzkriterium aus `.workflow/artifacts/ticket.md` ist durch mindestens einen der oben genannten Tests oder einen Kommando-Exit-Code belegt.
