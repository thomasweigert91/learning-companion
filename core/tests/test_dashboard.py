"""Dashboard: korrekte Aggregation und strikte Isolation zwischen Nutzern."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Goal, LearningSession, Tag

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"

# Zwei aufeinanderfolgende Kalenderwochen; beide Daten sind Dienstage, der von
# TruncWeek erwartete Wochenbeginn ist also der jeweilige Montag davor.
WOCHE_1_MONTAG = datetime.date(2026, 9, 14)
WOCHE_2_MONTAG = datetime.date(2026, 9, 21)
TAG_IN_WOCHE_1 = datetime.date(2026, 9, 15)
TAG_IN_WOCHE_1_B = datetime.date(2026, 9, 16)
TAG_IN_WOCHE_2 = datetime.date(2026, 9, 22)


class DashboardDatenTestCase(TestCase):
    """Nutzer A mit bekannter Datenlage, Nutzer B als Stoerfaktor.

    Nutzer B bekommt dieselben Tags, aber andere Dauern und andere Status. Ein
    fehlender Scoping-Filter wuerde die Zahlen von A dadurch zwangslaeufig
    verschieben -- genau darauf zielen die Isolations-Tests.
    """

    # Erwartungswerte fuer Nutzer A, an einer Stelle gepflegt.
    ERWARTET_PLANNED = 2
    ERWARTET_IN_PROGRESS = 1
    ERWARTET_DONE = 0
    ERWARTET_PYTHON = 90
    ERWARTET_DJANGO = 75
    ERWARTET_WOCHE_1 = 90
    ERWARTET_WOCHE_2 = 65
    ERWARTET_MINUTEN_GESAMT = 155
    ERWARTET_SESSIONS_GESAMT = 4
    ERWARTET_GOALS_GESAMT = 3

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.tag_python = Tag.objects.create(name="Python")
        cls.tag_django = Tag.objects.create(name="Django")

        # --- Nutzer A: 2x planned, 1x in-progress, 0x done -------------------
        cls.goal_a1 = Goal.objects.create(
            user=cls.user_a, title="A: Ziel 1", status=Goal.Status.PLANNED
        )
        Goal.objects.create(
            user=cls.user_a, title="A: Ziel 2", status=Goal.Status.PLANNED
        )
        cls.goal_a3 = Goal.objects.create(
            user=cls.user_a, title="A: Ziel 3", status=Goal.Status.IN_PROGRESS
        )

        # Woche 1: 60 + 30 = 90 Minuten
        session = LearningSession.objects.create(
            goal=cls.goal_a1, date=TAG_IN_WOCHE_1, duration=60
        )
        session.tags.add(cls.tag_python)

        # Mehrfach getaggt: zaehlt in Python UND Django ein.
        session = LearningSession.objects.create(
            goal=cls.goal_a1, date=TAG_IN_WOCHE_1_B, duration=30
        )
        session.tags.add(cls.tag_python, cls.tag_django)

        # Woche 2: 45 + 20 = 65 Minuten
        session = LearningSession.objects.create(
            goal=cls.goal_a3, date=TAG_IN_WOCHE_2, duration=45
        )
        session.tags.add(cls.tag_django)

        # Bewusst ohne Tag: darf keine None-Kategorie erzeugen, muss aber in
        # Wochen- und Gesamtsumme einfliessen.
        LearningSession.objects.create(
            goal=cls.goal_a3, date=TAG_IN_WOCHE_2, duration=20
        )

        # --- Nutzer B: abweichende Zahlen, gleiche Tags und Daten ------------
        goal_b1 = Goal.objects.create(
            user=cls.user_b, title="B: Ziel 1", status=Goal.Status.DONE
        )
        Goal.objects.create(
            user=cls.user_b, title="B: Ziel 2", status=Goal.Status.DONE
        )
        Goal.objects.create(
            user=cls.user_b, title="B: Ziel 3", status=Goal.Status.PLANNED
        )

        session = LearningSession.objects.create(
            goal=goal_b1, date=TAG_IN_WOCHE_1, duration=500
        )
        session.tags.add(cls.tag_python, cls.tag_django)

        session = LearningSession.objects.create(
            goal=goal_b1, date=TAG_IN_WOCHE_2, duration=700
        )
        session.tags.add(cls.tag_django)

    def setUp(self):
        self.client.force_login(self.user_a)
        self.url = reverse("core:dashboard")

    def kontext(self):
        """Rendert das Dashboard als Nutzer A und gibt den Kontext zurueck."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.context

    def status_map(self):
        return {
            zeile["status"]: zeile["anzahl"]
            for zeile in self.kontext()["goals_nach_status"]
        }

    def tag_map(self):
        return {
            zeile["tags__name"]: zeile["minuten"]
            for zeile in self.kontext()["zeit_je_tag"]
        }

    def wochen_map(self):
        return {
            zeile["woche"]: zeile["minuten"]
            for zeile in self.kontext()["zeit_je_woche"]
        }


class DashboardZugriffTests(DashboardDatenTestCase):
    def test_anonym_wird_umgeleitet(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('core:login')}?next={self.url}")

    def test_angemeldet_erreichbar(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/dashboard.html")

    def test_navbar_enthaelt_dashboard_link(self):
        response = self.client.get(reverse("core:goal_list"))
        self.assertContains(response, f'href="{self.url}"')


class GoalsNachStatusTests(DashboardDatenTestCase):
    def test_zaehlung_je_status(self):
        self.assertEqual(
            self.status_map(),
            {
                Goal.Status.PLANNED: self.ERWARTET_PLANNED,
                Goal.Status.IN_PROGRESS: self.ERWARTET_IN_PROGRESS,
                Goal.Status.DONE: self.ERWARTET_DONE,
            },
        )

    def test_status_ohne_goals_wird_mit_null_ausgewiesen(self):
        # "done" hat bei Nutzer A kein Goal und darf trotzdem nicht fehlen.
        self.assertIn(Goal.Status.DONE, self.status_map())
        self.assertEqual(self.status_map()[Goal.Status.DONE], 0)

    def test_reihenfolge_folgt_den_status_choices(self):
        zeilen = [zeile["status"] for zeile in self.kontext()["goals_nach_status"]]
        self.assertEqual(zeilen, list(Goal.Status.values))


class ZeitJeTagTests(DashboardDatenTestCase):
    def test_summe_je_tag(self):
        self.assertEqual(
            self.tag_map(),
            {"Python": self.ERWARTET_PYTHON, "Django": self.ERWARTET_DJANGO},
        )

    def test_session_ohne_tag_erzeugt_keine_leere_gruppe(self):
        self.assertNotIn(None, self.tag_map())

    def test_absteigend_nach_minuten_sortiert(self):
        minuten = [zeile["minuten"] for zeile in self.kontext()["zeit_je_tag"]]
        self.assertEqual(minuten, sorted(minuten, reverse=True))


class ZeitJeWocheTests(DashboardDatenTestCase):
    def test_summe_je_kalenderwoche(self):
        self.assertEqual(
            self.wochen_map(),
            {
                WOCHE_1_MONTAG: self.ERWARTET_WOCHE_1,
                WOCHE_2_MONTAG: self.ERWARTET_WOCHE_2,
            },
        )

    def test_aufsteigend_sortiert(self):
        wochen = [zeile["woche"] for zeile in self.kontext()["zeit_je_woche"]]
        self.assertEqual(wochen, [WOCHE_1_MONTAG, WOCHE_2_MONTAG])

    def test_wochenbeginn_ist_montag(self):
        for woche in self.wochen_map():
            self.assertEqual(woche.weekday(), 0, f"{woche} ist kein Montag")


class KpiTests(DashboardDatenTestCase):
    def test_kpi_summen(self):
        kontext = self.kontext()
        self.assertEqual(kontext["goals_gesamt"], self.ERWARTET_GOALS_GESAMT)
        self.assertEqual(kontext["sessions_gesamt"], self.ERWARTET_SESSIONS_GESAMT)
        self.assertEqual(kontext["minuten_gesamt"], self.ERWARTET_MINUTEN_GESAMT)

    def test_wochensummen_ergeben_die_gesamtzeit(self):
        self.assertEqual(
            sum(self.wochen_map().values()), self.ERWARTET_MINUTEN_GESAMT
        )


class IsolationsTests(DashboardDatenTestCase):
    """Die Daten von Nutzer B duerfen in keine Kennzahl von A einfliessen."""

    def test_fremde_goals_aendern_status_zaehlung_nicht(self):
        # B hat zwei "done"-Goals -- bei A muss "done" trotzdem 0 bleiben.
        self.assertEqual(self.status_map()[Goal.Status.DONE], 0)
        self.assertEqual(self.status_map()[Goal.Status.PLANNED], self.ERWARTET_PLANNED)

    def test_fremde_sessions_aendern_tag_summen_nicht(self):
        self.assertEqual(
            self.tag_map(),
            {"Python": self.ERWARTET_PYTHON, "Django": self.ERWARTET_DJANGO},
        )

    def test_fremde_sessions_aendern_wochen_summen_nicht(self):
        self.assertEqual(
            self.wochen_map(),
            {
                WOCHE_1_MONTAG: self.ERWARTET_WOCHE_1,
                WOCHE_2_MONTAG: self.ERWARTET_WOCHE_2,
            },
        )

    def test_fremde_daten_aendern_kpis_nicht(self):
        kontext = self.kontext()
        self.assertEqual(kontext["goals_gesamt"], self.ERWARTET_GOALS_GESAMT)
        self.assertEqual(kontext["sessions_gesamt"], self.ERWARTET_SESSIONS_GESAMT)
        self.assertEqual(kontext["minuten_gesamt"], self.ERWARTET_MINUTEN_GESAMT)

    def test_nutzer_b_sieht_seine_eigenen_zahlen(self):
        """Gegenprobe: B darf nicht etwa das Dashboard von A sehen."""
        self.client.force_login(self.user_b)
        kontext = self.kontext()
        self.assertEqual(kontext["minuten_gesamt"], 1200)
        self.assertEqual(
            {
                zeile["status"]: zeile["anzahl"]
                for zeile in kontext["goals_nach_status"]
            },
            {
                Goal.Status.PLANNED: 1,
                Goal.Status.IN_PROGRESS: 0,
                Goal.Status.DONE: 2,
            },
        )


class LeeresDashboardTests(DashboardDatenTestCase):
    """Ein Nutzer ohne jede Datenlage -- trotz Daten von A und B im System."""

    def setUp(self):
        self.user_leer = User.objects.create_user(
            username="nutzer_leer", password=PASSWORT
        )
        self.client.force_login(self.user_leer)
        self.url = reverse("core:dashboard")

    def test_nutzer_ohne_daten(self):
        kontext = self.kontext()
        self.assertEqual(kontext["goals_gesamt"], 0)
        self.assertEqual(kontext["sessions_gesamt"], 0)
        # Sum() liefert None statt 0, wenn nichts zu summieren ist.
        self.assertEqual(kontext["minuten_gesamt"], 0)
        self.assertEqual(kontext["zeit_je_tag"], [])
        self.assertEqual(kontext["zeit_je_woche"], [])

    def test_alle_status_stehen_mit_null_da(self):
        self.assertEqual(
            self.status_map(),
            {
                Goal.Status.PLANNED: 0,
                Goal.Status.IN_PROGRESS: 0,
                Goal.Status.DONE: 0,
            },
        )

    def test_maxima_sind_null_und_verursachen_keinen_fehler(self):
        kontext = self.kontext()
        self.assertEqual(kontext["max_status_anzahl"], 0)
        self.assertEqual(kontext["max_tag_minuten"], 0)
        self.assertEqual(kontext["max_wochen_minuten"], 0)

    def test_hinweis_statt_leerer_tabelle(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Noch keine Lernziele angelegt.")
        self.assertContains(response, "Noch keine Lernsitzungen erfasst.")
