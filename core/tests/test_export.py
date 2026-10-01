"""Export Center: CSV, Markdown-ZIP und JSON-Dump -- Format, Header und Isolation."""

import csv
import datetime
import io
import json
import re
import zipfile

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import FileResponse, StreamingHttpResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import AIFeedback, Flashcard, Goal, LearningSession, Resource, Tag

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
# Steht in allen Texten von Nutzer B. Taucht er in einem Export von A auf, ist
# die Isolation gebrochen.
FREMD = "FREMD"

DOWNLOADS = ("core:export_sessions_csv", "core:export_goals_zip", "core:export_json")
ALLE_ROUTEN = ("core:export_center", *DOWNLOADS)
CSV_HEADER = ["Goal", "Date", "Duration (min)", "Tags", "Notes"]

# Format aus core/_nav_link.html (siehe test_ui.py).
NAV_LINK = re.compile(r'<a class="nav-link(?P<active> active)?" href="(?P<href>[^"]+)"')


def heute():
    return f"{timezone.localdate():%Y-%m-%d}"


def streaming_text(response):
    return b"".join(response.streaming_content).decode("utf-8")


def csv_zeilen(response):
    return list(csv.reader(io.StringIO(streaming_text(response).removeprefix("﻿"))))


def zip_dateien(response):
    archiv = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))
    return {name: archiv.read(name).decode("utf-8") for name in archiv.namelist()}


class ExportTestCase(TestCase):
    """Nutzer A mit bekannter Datenlage, Nutzer B mit markierten Fremddaten.

    B nutzt dieselben Tags wie A; ein fehlender Scoping-Filter wuerde ueber die
    gemeinsamen Tags sofort Fremddaten in den Export ziehen.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(
            username="nutzer_a", email="a@example.org", password=PASSWORT
        )
        cls.user_b = User.objects.create_user(
            username="nutzer_b", email="b@example.org", password=PASSWORT
        )
        cls.user_a.profile.name = "Änne Ärger"
        cls.user_a.profile.cohort = "Kohorte 7"
        cls.user_a.profile.save()

        cls.python = Tag.objects.create(name="Python")
        cls.django = Tag.objects.create(name="Django")
        cls.user_a.profile.focus_areas.add(cls.python)

        # --- Nutzer A ---------------------------------------------------------
        cls.goal_orm = Goal.objects.create(
            user=cls.user_a,
            title='Django: "ORM" #1',
            description="Querysets verstehen",
            status=Goal.Status.IN_PROGRESS,
        )
        cls.goal_leer = Goal.objects.create(user=cls.user_a, title="Über Testing")

        # Bewusst nicht chronologisch angelegt: der Export sortiert selbst.
        cls.session_spaet = LearningSession.objects.create(
            goal=cls.goal_orm,
            date=datetime.date(2026, 9, 22),
            duration=45,
            notes='Zeile 1\nZeile 2, mit Komma und "Zitat"',
        )
        cls.session_spaet.tags.add(cls.python, cls.django)
        cls.session_frueh = LearningSession.objects.create(
            goal=cls.goal_orm,
            date=datetime.date(2026, 9, 15),
            duration=60,
            notes="=SUMME(A1:A9)",
        )
        cls.session_frueh.tags.add(cls.python)

        Resource.objects.create(
            goal=cls.goal_orm,
            url="https://docs.djangoproject.com/en/5.2/ref/models/querysets/",
            title="QuerySet [API]",
            type=Resource.Type.DOC,
        )
        AIFeedback.objects.create(
            goal=cls.goal_orm,
            feedback_type=AIFeedback.FeedbackType.SUMMARY,
            content="Guter Fortschritt",
        )
        Flashcard.objects.create(
            goal=cls.goal_orm, question="Was macht annotate()?", answer="Pro Zeile"
        )

        # --- Nutzer B: Fremddaten in jedem Modell --------------------------------
        goal_b = Goal.objects.create(
            user=cls.user_b, title=f"{FREMD} Ziel", description=f"{FREMD} Beschreibung"
        )
        session_b = LearningSession.objects.create(
            goal=goal_b, date=datetime.date(2026, 9, 16), duration=999, notes=f"{FREMD} Notiz"
        )
        session_b.tags.add(cls.python, cls.django)
        Resource.objects.create(
            goal=goal_b, url="https://example.org/fremd", title=f"{FREMD} Ressource"
        )
        AIFeedback.objects.create(
            goal=goal_b,
            feedback_type=AIFeedback.FeedbackType.SUMMARY,
            content=f"{FREMD} KI",
        )
        Flashcard.objects.create(goal=goal_b, question=f"{FREMD} Frage", answer=f"{FREMD} Antwort")

    def setUp(self):
        self.client.force_login(self.user_a)

    def get(self, url_name):
        return self.client.get(reverse(url_name))


# --- Zugriff ------------------------------------------------------------------


class ExportZugriffTests(ExportTestCase):
    def test_anonym_wird_zum_login_umgeleitet(self):
        self.client.logout()
        for url_name in ALLE_ROUTEN:
            with self.subTest(url_name=url_name):
                url = reverse(url_name)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, f"{reverse('core:login')}?next={url}")

    def test_downloads_nur_per_get(self):
        for url_name in DOWNLOADS:
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.post(reverse(url_name)).status_code, 405)

    def test_downloads_werden_nicht_gecacht(self):
        for url_name in DOWNLOADS:
            with self.subTest(url_name=url_name):
                self.assertIn("no-store", self.get(url_name)["Cache-Control"])


# --- Export-Seite & Navigation ---------------------------------------------------


class ExportSeiteTests(ExportTestCase):
    def test_seite_zeigt_umfang_und_drei_downloads(self):
        response = self.get("core:export_center")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sessions_anzahl"], 2)
        self.assertEqual(response.context["goals_anzahl"], 2)
        for url_name in DOWNLOADS:
            self.assertContains(response, f'href="{reverse(url_name)}" download')

    def test_menuepunkt_export_ist_aktiv(self):
        html = self.get("core:export_center").content.decode()
        links = {m["href"]: bool(m["active"]) for m in NAV_LINK.finditer(html)}
        self.assertTrue(links["/export/"])
        self.assertEqual(sum(links.values()), 1)

    def test_menuepunkt_auf_anderen_seiten_inaktiv(self):
        html = self.get("core:dashboard").content.decode()
        links = {m["href"]: bool(m["active"]) for m in NAV_LINK.finditer(html)}
        self.assertFalse(links["/export/"])

    def test_eine_h1_und_versteckte_icons(self):
        html = self.get("core:export_center").content.decode()
        self.assertEqual(html.count("<h1"), 1)
        for icon in re.findall(r'<i class="bi [^"]*"[^>]*>', html):
            self.assertIn('aria-hidden="true"', icon)


# --- CSV ----------------------------------------------------------------------


class SessionsCSVTests(ExportTestCase):
    def test_streaming_response_mit_headern(self):
        response = self.get("core:export_sessions_csv")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, StreamingHttpResponse)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="learning-companion-sessions-{heute()}.csv"',
        )

    def test_bom_und_exakter_header(self):
        text = streaming_text(self.get("core:export_sessions_csv"))
        self.assertTrue(text.startswith("﻿"))
        self.assertEqual(
            text.removeprefix("﻿").split("\r\n")[0], "Goal,Date,Duration (min),Tags,Notes"
        )

    def test_eine_zeile_je_session_chronologisch(self):
        zeilen = csv_zeilen(self.get("core:export_sessions_csv"))
        self.assertEqual(
            zeilen[1:],
            [
                ['Django: "ORM" #1', "2026-09-15", "60", "Python", "'=SUMME(A1:A9)"],
                [
                    'Django: "ORM" #1',
                    "2026-09-22",
                    "45",
                    "Django; Python",
                    'Zeile 1\nZeile 2, mit Komma und "Zitat"',
                ],
            ],
        )

    def test_formel_praefixe_werden_neutralisiert(self):
        goal = Goal.objects.create(user=self.user_a, title="@Ziel")
        for praefix in ("+", "-", "\t"):
            LearningSession.objects.create(
                goal=goal, date=datetime.date(2026, 10, 1), duration=1, notes=f"{praefix}1"
            )
        zeilen = csv_zeilen(self.get("core:export_sessions_csv"))
        neue = [z for z in zeilen if z[0] == "'@Ziel"]
        self.assertEqual(sorted(z[4] for z in neue), sorted(["'+1", "'-1", "'\t1"]))

    def test_ohne_sessions_nur_header(self):
        self.client.force_login(User.objects.create_user(username="neu", password=PASSWORT))
        self.assertEqual(csv_zeilen(self.get("core:export_sessions_csv")), [CSV_HEADER])

    def test_keine_fremden_sessions(self):
        text = streaming_text(self.get("core:export_sessions_csv"))
        self.assertNotIn(FREMD, text)
        self.assertNotIn("999", text)

    def test_abfragezahl_unabhaengig_von_sessionzahl(self):
        def abfragen():
            with CaptureQueriesContext(connection) as ctx:
                streaming_text(self.get("core:export_sessions_csv"))
            return len(ctx)

        vorher = abfragen()
        for tag in range(5):
            session = LearningSession.objects.create(
                goal=self.goal_leer, date=datetime.date(2026, 9, 1 + tag), duration=10
            )
            session.tags.add(self.django)
        self.assertEqual(abfragen(), vorher)


# --- Markdown-ZIP -------------------------------------------------------------


class GoalsZipTests(ExportTestCase):
    def test_file_response_mit_headern(self):
        response = self.get("core:export_goals_zip")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="learning-companion-goals-{heute()}.zip"',
        )

    def test_gueltiges_zip_mit_einer_datei_je_goal(self):
        dateien = zip_dateien(self.get("core:export_goals_zip"))
        self.assertEqual(
            sorted(dateien),
            sorted(
                [
                    f"goals/{self.goal_orm.pk}-django-orm-1.md",
                    f"goals/{self.goal_leer.pk}-uber-testing.md",
                ]
            ),
        )

    def test_gleicher_titel_und_leerer_slug(self):
        doppelt = Goal.objects.create(user=self.user_a, title="Über Testing")
        ohne_slug = Goal.objects.create(user=self.user_a, title="!!!")
        dateien = zip_dateien(self.get("core:export_goals_zip"))
        self.assertEqual(len(dateien), 4)
        self.assertIn(f"goals/{doppelt.pk}-uber-testing.md", dateien)
        self.assertIn(f"goals/{ohne_slug.pk}-goal.md", dateien)

    def markdown(self, goal):
        dateien = zip_dateien(self.get("core:export_goals_zip"))
        return next(
            inhalt for name, inhalt in dateien.items() if name.startswith(f"goals/{goal.pk}-")
        )

    def test_frontmatter(self):
        zeilen = self.markdown(self.goal_orm).splitlines()
        ende = zeilen.index("---", 1)
        self.assertEqual(zeilen[0], "---")
        frontmatter = zeilen[1:ende]
        self.assertEqual(frontmatter[0], f"id: {self.goal_orm.pk}")
        self.assertEqual(frontmatter[1], 'title: "Django: \\"ORM\\" #1"')
        self.assertEqual(frontmatter[2], 'status: "in-progress"')
        self.assertRegex(
            frontmatter[3], r"^created: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+0[12]:00$"
        )
        self.assertTrue(frontmatter[4].startswith("updated: "))
        self.assertEqual(frontmatter[5:], ["sessions: 2", "total_minutes: 105"])

    def test_titel_im_frontmatter_ist_gueltiger_string(self):
        zeile = self.markdown(self.goal_orm).splitlines()[2]
        self.assertEqual(json.loads(zeile.removeprefix("title: ")), self.goal_orm.title)

    def test_inhalt_mit_ressourcen_und_sessions(self):
        md = self.markdown(self.goal_orm)
        self.assertIn('\n# Django: "ORM" #1\n\nQuerysets verstehen\n', md)
        self.assertIn(
            "- [QuerySet \\[API\\]](<https://docs.djangoproject.com/en/5.2/ref/models/querysets/>)"
            " -- Dokumentation",
            md,
        )
        self.assertLess(
            md.index("### 2026-09-15 -- 60 Min."), md.index("### 2026-09-22 -- 45 Min.")
        )
        self.assertIn("Tags: Django, Python", md)
        self.assertIn("Zeile 1\nZeile 2", md)
        self.assertIn("=SUMME(A1:A9)", md)

    def test_leeres_goal_zeigt_hinweise(self):
        md = self.markdown(self.goal_leer)
        self.assertIn("_Keine Beschreibung._", md)
        self.assertIn("## Ressourcen\n\n_Keine Ressourcen._", md)
        self.assertIn("## Lernsitzungen\n\n_Keine Lernsitzungen._", md)
        self.assertIn("sessions: 0\ntotal_minutes: 0\n", md)

    def test_ohne_goals_leeres_zip(self):
        self.client.force_login(User.objects.create_user(username="neu", password=PASSWORT))
        response = self.get("core:export_goals_zip")
        inhalt = b"".join(response.streaming_content)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(inhalt)))
        self.assertEqual(zipfile.ZipFile(io.BytesIO(inhalt)).namelist(), [])

    def test_keine_fremden_goals(self):
        dateien = zip_dateien(self.get("core:export_goals_zip"))
        self.assertEqual(len(dateien), 2)
        for name, inhalt in dateien.items():
            self.assertNotIn(FREMD.lower(), name)
            self.assertNotIn(FREMD, inhalt)


# --- JSON-Dump ----------------------------------------------------------------


class JSONDumpTests(ExportTestCase):
    def dump(self):
        return json.loads(self.get("core:export_json").content)

    def test_response_mit_headern(self):
        response = self.get("core:export_json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="learning-companion-data-{heute()}.json"',
        )

    def test_utf8_ohne_escapes_und_eingerueckt(self):
        text = self.get("core:export_json").content.decode("utf-8")
        self.assertIn("Änne Ärger", text)
        self.assertIn('\n  "format_version": 1', text)

    def test_konto_und_profil(self):
        dump = self.dump()
        self.assertEqual(dump["format_version"], 1)
        self.assertIsNotNone(datetime.datetime.fromisoformat(dump["exported_at"]))
        self.assertEqual(set(dump["user"]), {"username", "email", "date_joined"})
        self.assertEqual(dump["user"]["username"], "nutzer_a")
        self.assertEqual(dump["user"]["email"], "a@example.org")
        self.assertEqual(dump["profile"]["name"], "Änne Ärger")
        self.assertEqual(dump["profile"]["cohort"], "Kohorte 7")
        self.assertEqual(dump["profile"]["focus_areas"], ["Python"])

    def test_goals_mit_allen_kinddaten(self):
        goals = {g["id"]: g for g in self.dump()["goals"]}
        self.assertEqual(set(goals), {self.goal_orm.pk, self.goal_leer.pk})

        orm = goals[self.goal_orm.pk]
        self.assertEqual(orm["title"], 'Django: "ORM" #1')
        self.assertEqual(orm["status"], "in-progress")
        self.assertEqual(
            [(s["date"], s["duration_minutes"], s["tags"]) for s in orm["sessions"]],
            [("2026-09-15", 60, ["Python"]), ("2026-09-22", 45, ["Django", "Python"])],
        )
        self.assertEqual(orm["sessions"][0]["notes"], "=SUMME(A1:A9)")
        self.assertEqual(orm["resources"][0]["title"], "QuerySet [API]")
        self.assertEqual(orm["resources"][0]["type"], "doc")
        self.assertEqual(orm["ai_feedbacks"][0]["content"], "Guter Fortschritt")
        self.assertEqual(orm["ai_feedbacks"][0]["feedback_type"], "summary")
        self.assertEqual(orm["flashcards"][0]["question"], "Was macht annotate()?")
        self.assertFalse(orm["flashcards"][0]["is_mastered"])

        leer = goals[self.goal_leer.pk]
        for schluessel in ("sessions", "resources", "ai_feedbacks", "flashcards"):
            self.assertEqual(leer[schluessel], [])

    def test_statistiken(self):
        self.assertEqual(
            self.dump()["statistics"],
            {
                "goals_total": 2,
                "sessions_total": 2,
                "minutes_total": 105,
                "goals_by_status": {"planned": 1, "in-progress": 1, "done": 0},
                # Die Sitzung mit beiden Tags zaehlt in beide Kategorien.
                "minutes_by_tag": [
                    {"tag": "Python", "minutes": 105},
                    {"tag": "Django", "minutes": 45},
                ],
            },
        )

    def test_keine_sicherheitsrelevanten_felder(self):
        text = self.get("core:export_json").content.decode("utf-8")
        for verboten in ("password", "pbkdf2", "is_staff", "is_superuser", "last_login"):
            with self.subTest(feld=verboten):
                self.assertNotIn(verboten, text)

    def test_keine_fremddaten(self):
        text = self.get("core:export_json").content.decode("utf-8")
        self.assertNotIn(FREMD, text)
        self.assertNotIn("nutzer_b", text)
        self.assertNotIn("b@example.org", text)

    def test_abfragezahl_unabhaengig_von_goalzahl(self):
        def abfragen():
            with CaptureQueriesContext(connection) as ctx:
                self.get("core:export_json")
            return len(ctx)

        vorher = abfragen()
        for nummer in range(3):
            goal = Goal.objects.create(user=self.user_a, title=f"Zusatz {nummer}")
            session = LearningSession.objects.create(
                goal=goal, date=datetime.date(2026, 9, 1), duration=5
            )
            session.tags.add(self.python)
            Resource.objects.create(goal=goal, url="https://example.org", title="R")
            Flashcard.objects.create(goal=goal, question="F", answer="A")
        self.assertEqual(abfragen(), vorher)
