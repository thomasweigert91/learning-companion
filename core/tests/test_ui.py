"""Bootstrap-UI: Einbindung, Navigation, Formular-Darstellung, Barrierefreiheit."""

import datetime
import re

from django import forms
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.forms import GoalForm, ResourceForm
from core.models import Goal, LearningSession, Resource, Tag
from core.templatetags.ui import bs_widget, has_required

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
DATUM = datetime.date(2026, 9, 15)

# Format aus core/_nav_link.html: <a class="nav-link[ active]" href="..."[ aria-current="page"]>
NAV_LINK = re.compile(
    r'<a class="nav-link(?P<active> active)?" href="(?P<href>[^"]+)"'
    r'(?P<current> aria-current="page")?>'
)


class UiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(
            user=cls.user, title="Django lernen", status=Goal.Status.IN_PROGRESS
        )
        cls.tag = Tag.objects.create(name="Python")

    def setUp(self):
        self.client.force_login(self.user)

    def html(self, url_name, *args):
        response = self.client.get(reverse(url_name, args=args))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def nav_links(self, html):
        """{href: (active, aria_current)} fuer alle Links der Hauptnavigation."""
        return {
            m["href"]: (bool(m["active"]), bool(m["current"]))
            for m in NAV_LINK.finditer(html)
        }


class BootstrapEinbindungTests(UiTestCase):
    def test_bootstrap_css_und_js_mit_sri(self):
        html = self.html("core:dashboard")
        for ressource in (
            "bootstrap@5.3.8/dist/css/bootstrap.min.css",
            "bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js",
            "bootstrap-icons@1.13.1/font/bootstrap-icons.min.css",
        ):
            with self.subTest(ressource=ressource):
                # integrity und crossorigin muessen am selben Tag stehen.
                muster = re.compile(
                    re.escape(ressource) + r'"\s+integrity="sha384-[A-Za-z0-9+/=]{64}"'
                    r'\s+crossorigin="anonymous"'
                )
                self.assertRegex(html, muster)

    def test_script_steht_am_ende_des_body(self):
        html = self.html("core:dashboard")
        self.assertLess(html.index("<main"), html.index("bootstrap.bundle.min.js"))

    def test_skip_link_und_main_landmark(self):
        html = self.html("core:dashboard")
        self.assertIn('href="#main-content"', html)
        self.assertIn('<main id="main-content"', html)
        # Der Skip-Link muss vor der Navigation stehen, um sie zu ueberspringen.
        self.assertLess(html.index('href="#main-content"'), html.index("<nav"))


class NavigationTests(UiTestCase):
    def test_aktiver_link_dashboard(self):
        links = self.nav_links(self.html("core:dashboard"))
        self.assertEqual(links["/dashboard/"], (True, True))
        self.assertEqual(links["/goals/"], (False, False))
        self.assertEqual(links["/sessions/"], (False, False))

    def test_goal_detail_markiert_goals(self):
        links = self.nav_links(self.html("core:goal_detail", self.goal.pk))
        self.assertEqual(links["/goals/"], (True, True))
        self.assertEqual(links["/dashboard/"], (False, False))

    def test_resource_route_markiert_goals(self):
        resource = Resource.objects.create(
            goal=self.goal, url="https://example.org", title="Doku"
        )
        links = self.nav_links(self.html("core:resource_delete", resource.pk))
        self.assertEqual(links["/goals/"], (True, True))

    def test_session_seiten_markieren_sessions(self):
        for url_name in ("core:session_list", "core:session_create"):
            with self.subTest(url_name=url_name):
                links = self.nav_links(self.html(url_name))
                self.assertEqual(links["/sessions/"], (True, True))
                self.assertEqual(links["/goals/"], (False, False))

    def test_genau_ein_nav_link_aktiv(self):
        links = self.nav_links(self.html("core:goal_list"))
        self.assertEqual(sum(aktiv for aktiv, _ in links.values()), 1)

    def test_logout_ist_post_formular_im_dropdown(self):
        html = self.html("core:dashboard")
        dropdown = html[html.index('class="dropdown-menu') :]
        self.assertRegex(
            dropdown,
            r'<form action="/accounts/logout/" method="post">\s*'
            r'<input type="hidden" name="csrfmiddlewaretoken"',
        )

    def test_anonym_sieht_login_und_registrieren(self):
        self.client.logout()
        html = self.html("core:home")
        self.assertNotIn("dropdown-toggle", html)
        self.assertIn('href="/accounts/login/"', html)
        self.assertIn('href="/accounts/register/"', html)


class FormularDarstellungTests(UiTestCase):
    def test_felder_mit_bootstrap_klassen(self):
        html = self.html("core:goal_create")
        self.assertRegex(html, r'<input type="text" name="title" [^>]*class="form-control"')
        self.assertRegex(html, r'<select name="status" [^>]*class="form-select"')
        # IDs unveraendert -- die Labels zeigen weiter auf dieselben Felder.
        self.assertIn('id="id_title"', html)
        self.assertIn('for="id_title"', html)
        self.assertIn('id="id_status"', html)

    def test_fehler_markiert_feld(self):
        response = self.client.post(
            reverse("core:goal_create"), {"title": "", "status": "planned"}
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        feld = re.search(r'<input type="text" name="title"[^>]*>', html).group(0)
        self.assertIn("is-invalid", feld)
        self.assertIn('aria-invalid="true"', feld)
        self.assertIn('aria-describedby="id_title_error"', feld)
        self.assertIn('id="id_title_error"', html)

    def test_mehrfachauswahl_als_fieldset(self):
        html = self.html("core:session_create")
        self.assertIn("<fieldset", html)
        self.assertRegex(html, r"<legend[^>]*>\s*Tags")
        # Name, Wert und ID wie beim Django-Widget.
        self.assertRegex(
            html,
            rf'name="tags" value="{self.tag.pk}"\s+id="id_tags_0"',
        )

    def test_gesetzter_tag_ist_vorausgewaehlt(self):
        session = LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
        session.tags.add(self.tag)

        html = self.html("core:session_edit", session.pk)

        checkbox = re.search(r'<input type="checkbox"[^>]*id="id_tags_0"[^>]*>', html).group(0)
        self.assertIn("checked", checkbox)

    def test_chip_auswahl_laesst_sich_absenden(self):
        """Das selbst gerenderte Feld muss vom Formular wieder angenommen werden."""
        response = self.client.post(
            reverse("core:session_create"),
            {
                "goal": self.goal.pk,
                "date": "2026-09-15",
                "duration": 30,
                "tags": [self.tag.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(LearningSession.objects.get().tags.all()), [self.tag]
        )

    def test_login_formular_gestylt(self):
        self.client.logout()
        html = self.html("core:login")
        self.assertRegex(html, r'<input type="text" name="username"[^>]*class="form-control"')
        self.assertRegex(html, r'<input type="password" name="password"[^>]*class="form-control"')
        self.assertIn('id="id_username"', html)

    def test_pflichtfeld_hinweis(self):
        self.assertIn("Pflichtfelder sind mit", self.html("core:goal_create"))

    def test_login_ohne_pflichtfeld_hinweis(self):
        self.client.logout()
        self.assertNotIn("Pflichtfelder sind mit", self.html("core:login"))


class TemplateTagTests(TestCase):
    def test_bs_widget_klassen_je_widget_typ(self):
        class Beispiel(forms.Form):
            text = forms.CharField()
            auswahl = forms.ChoiceField(choices=[("a", "A")])
            haken = forms.BooleanField(required=False)

        form = Beispiel()
        self.assertIn('class="form-control"', bs_widget(form["text"]))
        self.assertIn('class="form-select"', bs_widget(form["auswahl"]))
        self.assertIn('class="form-check-input"', bs_widget(form["haken"]))

    def test_bs_widget_behaelt_vorhandene_klasse_und_placeholder(self):
        class MitKlasse(forms.Form):
            feld = forms.CharField(widget=forms.TextInput(attrs={"class": "font-monospace"}))

        self.assertIn('class="font-monospace form-control"', bs_widget(MitKlasse()["feld"]))
        self.assertIn('placeholder="https://..."', bs_widget(ResourceForm()["url"]))

    def test_bs_widget_verknuepft_hilfetext(self):
        class MitHilfe(forms.Form):
            feld = forms.CharField(help_text="Kurz halten.")

        self.assertIn('aria-describedby="id_feld_helptext"', bs_widget(MitHilfe()["feld"]))

    def test_has_required(self):
        class Optional(forms.Form):
            feld = forms.CharField(required=False)

        self.assertTrue(has_required(GoalForm()))
        self.assertFalse(has_required(Optional()))


class SeitenDarstellungTests(UiTestCase):
    def test_status_badge_mit_text(self):
        Goal.objects.create(user=self.user, title="Fertig", status=Goal.Status.DONE)
        html = self.html("core:goal_list")
        self.assertRegex(html, r'text-bg-success">.*?</i>Erledigt</span>')

    def test_dashboard_progressbar_aria(self):
        LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
        html = self.html("core:dashboard")
        self.assertRegex(
            html,
            r'role="progressbar" aria-label="[^"]+"\s+aria-valuenow="100" '
            r'aria-valuemin="0" aria-valuemax="100"',
        )

    def test_tabellen_mit_caption_und_scope(self):
        LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
        for url_name in ("core:dashboard", "core:session_list"):
            with self.subTest(url_name=url_name):
                html = self.html(url_name)
                self.assertIn("<caption", html)
                self.assertIn('<th scope="col"', html)

    def test_session_liste_zeigt_tags_ohne_n_plus_1(self):
        def anzahl_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse("core:session_list"))
            return len(ctx.captured_queries)

        for _ in range(3):
            session = LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
            session.tags.add(self.tag)
        bei_drei = anzahl_queries()

        for _ in range(3):
            session = LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
            session.tags.add(self.tag)
        bei_sechs = anzahl_queries()

        self.assertEqual(bei_drei, bei_sechs)
        self.assertContains(
            self.client.get(reverse("core:session_list")),
            '<span class="badge rounded-pill text-bg-light border">Python</span>',
            count=6,
        )

    def test_externer_link_kuendigt_neuen_tab_an(self):
        Resource.objects.create(goal=self.goal, url="https://example.org", title="Doku")
        html = self.html("core:goal_detail", self.goal.pk)
        self.assertRegex(html, r'target="_blank"[^>]*>\s*Doku.*?oeffnet in neuem Tab')

    def test_icon_buttons_haben_zugaenglichen_namen(self):
        Resource.objects.create(goal=self.goal, url="https://example.org", title="Doku")
        html = self.html("core:goal_detail", self.goal.pk)
        self.assertIn('aria-label="Ressource Doku entfernen"', html)

    def test_dekorative_icons_sind_versteckt(self):
        for url_name in ("core:dashboard", "core:goal_list", "core:session_list", "core:home"):
            with self.subTest(url_name=url_name):
                html = self.html(url_name)
                for icon in re.findall(r'<i class="bi [^"]*"[^>]*>', html):
                    self.assertIn('aria-hidden="true"', icon)

    def test_genau_eine_h1_je_seite(self):
        session = LearningSession.objects.create(goal=self.goal, date=DATUM, duration=30)
        seiten = [
            ("core:home",),
            ("core:dashboard",),
            ("core:profile_detail",),
            ("core:profile_edit",),
            ("core:goal_list",),
            ("core:goal_create",),
            ("core:goal_detail", self.goal.pk),
            ("core:goal_delete", self.goal.pk),
            ("core:session_list",),
            ("core:session_detail", session.pk),
            ("core:session_delete", session.pk),
        ]
        for name, *args in seiten:
            with self.subTest(seite=name):
                self.assertEqual(self.html(name, *args).count("<h1"), 1)
