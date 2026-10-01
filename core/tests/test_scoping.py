"""Mandantentrennung: Nutzer A darf nicht an die Daten von Nutzer B."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Goal, LearningSession

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
DATUM = datetime.date(2026, 9, 15)


class ZweiNutzerTestCase(TestCase):
    """Basis: zwei Nutzer, je ein Goal und eine Session."""

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.goal_a = Goal.objects.create(
            user=cls.user_a, title="Ziel von A", status="planned"
        )
        cls.goal_b = Goal.objects.create(
            user=cls.user_b, title="Ziel von B", status="planned"
        )

        cls.session_a = LearningSession.objects.create(
            goal=cls.goal_a, date=DATUM, duration=60, notes="Notiz von A"
        )
        cls.session_b = LearningSession.objects.create(
            goal=cls.goal_b, date=DATUM, duration=30, notes="Notiz von B"
        )


class AnonymerZugriffTests(ZweiNutzerTestCase):
    """Alle zehn CRUD-Views muessen anonyme Aufrufe auf den Login umleiten."""

    def _pruefe_login_pflicht(self, url):
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('core:login')}?next={url}")

    def test_all_goal_views_require_login(self):
        urls = [
            reverse("core:goal_list"),
            reverse("core:goal_create"),
            reverse("core:goal_detail", args=[self.goal_a.pk]),
            reverse("core:goal_edit", args=[self.goal_a.pk]),
            reverse("core:goal_delete", args=[self.goal_a.pk]),
        ]
        self.assertEqual(len(urls), 5)
        for url in urls:
            with self.subTest(url=url):
                self._pruefe_login_pflicht(url)

    def test_all_session_views_require_login(self):
        urls = [
            reverse("core:session_list"),
            reverse("core:session_create"),
            reverse("core:session_detail", args=[self.session_a.pk]),
            reverse("core:session_edit", args=[self.session_a.pk]),
            reverse("core:session_delete", args=[self.session_a.pk]),
        ]
        self.assertEqual(len(urls), 5)
        for url in urls:
            with self.subTest(url=url):
                self._pruefe_login_pflicht(url)


class FremdzugriffGoalTests(ZweiNutzerTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_foreign_goal_detail_returns_404(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Ziel von B", status_code=404)

    def test_foreign_goal_edit_get_returns_404(self):
        response = self.client.get(reverse("core:goal_edit", args=[self.goal_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Ziel von B", status_code=404)

    def test_foreign_goal_edit_post_does_not_change_data(self):
        response = self.client.post(
            reverse("core:goal_edit", args=[self.goal_b.pk]),
            {"title": "Gekapert durch A", "description": "", "status": "done"},
        )

        self.assertEqual(response.status_code, 404)

        self.goal_b.refresh_from_db()
        self.assertEqual(self.goal_b.title, "Ziel von B")
        self.assertEqual(self.goal_b.status, "planned")

    def test_foreign_goal_delete_post_does_not_delete(self):
        response = self.client.post(reverse("core:goal_delete", args=[self.goal_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Goal.objects.filter(pk=self.goal_b.pk).exists())

    def test_foreign_goal_not_in_own_list(self):
        response = self.client.get(reverse("core:goal_list"))

        self.assertNotIn(self.goal_b, response.context["object_list"])


class FremdzugriffSessionTests(ZweiNutzerTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_foreign_session_detail_returns_404(self):
        response = self.client.get(
            reverse("core:session_detail", args=[self.session_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Notiz von B", status_code=404)

    def test_foreign_session_edit_get_returns_404(self):
        response = self.client.get(
            reverse("core:session_edit", args=[self.session_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Notiz von B", status_code=404)

    def test_foreign_session_edit_post_does_not_change_data(self):
        response = self.client.post(
            reverse("core:session_edit", args=[self.session_b.pk]),
            {
                "goal": self.goal_a.pk,
                "date": "2026-12-24",
                "duration": 999,
                "notes": "Gekapert durch A",
            },
        )

        self.assertEqual(response.status_code, 404)

        self.session_b.refresh_from_db()
        self.assertEqual(self.session_b.notes, "Notiz von B")
        self.assertEqual(self.session_b.duration, 30)
        self.assertEqual(self.session_b.goal, self.goal_b)

    def test_foreign_session_delete_post_does_not_delete(self):
        response = self.client.post(
            reverse("core:session_delete", args=[self.session_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(LearningSession.objects.filter(pk=self.session_b.pk).exists())

    def test_foreign_session_not_in_own_list(self):
        response = self.client.get(reverse("core:session_list"))

        self.assertNotIn(self.session_b, response.context["object_list"])


class GegenprobeTests(ZweiNutzerTestCase):
    """Das Scoping darf nicht einfach alles sperren.

    Ohne diese Gegenprobe waeren die 404-Tests oben auch durch eine komplett
    kaputte View trivial erfuellt.
    """

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_own_goal_and_session_remain_accessible(self):
        goal_response = self.client.get(
            reverse("core:goal_detail", args=[self.goal_a.pk])
        )
        self.assertEqual(goal_response.status_code, 200)
        self.assertContains(goal_response, "Ziel von A")

        session_response = self.client.get(
            reverse("core:session_detail", args=[self.session_a.pk])
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertContains(session_response, "Notiz von A")

    def test_own_goal_edit_and_delete_work(self):
        edit = self.client.post(
            reverse("core:goal_edit", args=[self.goal_a.pk]),
            {"title": "A bearbeitet", "description": "", "status": "done"},
        )
        self.assertEqual(edit.status_code, 302)
        self.goal_a.refresh_from_db()
        self.assertEqual(self.goal_a.title, "A bearbeitet")

        loeschen = self.client.post(reverse("core:goal_delete", args=[self.goal_a.pk]))
        self.assertEqual(loeschen.status_code, 302)
        self.assertFalse(Goal.objects.filter(pk=self.goal_a.pk).exists())
