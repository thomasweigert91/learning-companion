from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Goal

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"


class GoalModellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)

    def test_goal_str_returns_title(self):
        goal = Goal.objects.create(user=self.user, title="Django lernen")
        self.assertEqual(str(goal), "Django lernen")

    def test_goal_default_status_is_planned(self):
        goal = Goal.objects.create(user=self.user, title="Ohne Status")
        self.assertEqual(goal.status, Goal.Status.PLANNED)
        self.assertEqual(goal.status, "planned")

    def test_invalid_status_rejected_by_full_clean(self):
        goal = Goal(user=self.user, title="Kaputt", status="unsinn")
        with self.assertRaises(ValidationError) as ctx:
            goal.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

    def test_all_three_statuses_are_valid(self):
        for wert in ("planned", "in-progress", "done"):
            with self.subTest(status=wert):
                goal = Goal(user=self.user, title=f"Ziel {wert}", status=wert)
                goal.full_clean()  # darf nicht werfen


class GoalCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)
        cls.goal_a = Goal.objects.create(
            user=cls.user_a, title="Ziel von A", status=Goal.Status.PLANNED
        )
        cls.goal_b = Goal.objects.create(
            user=cls.user_b, title="Ziel von B", status=Goal.Status.DONE
        )

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_goal_list_shows_only_own_goals(self):
        response = self.client.get(reverse("core:goal_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.goal_a, response.context["object_list"])
        self.assertNotIn(self.goal_b, response.context["object_list"])
        self.assertContains(response, "Ziel von A")
        self.assertNotContains(response, "Ziel von B")

    def test_goal_create_assigns_current_user(self):
        response = self.client.post(
            reverse("core:goal_create"),
            {"title": "Neues Ziel", "description": "", "status": "planned"},
        )

        self.assertEqual(response.status_code, 302)
        goal = Goal.objects.get(title="Neues Ziel")
        self.assertEqual(goal.user, self.user_a)

    def test_goal_create_ignores_user_field_in_post(self):
        # Selbst wenn jemand "user" mitschickt, darf die Zuordnung nicht kippen.
        self.client.post(
            reverse("core:goal_create"),
            {
                "title": "Untergeschoben",
                "description": "",
                "status": "planned",
                "user": self.user_b.pk,
            },
        )

        goal = Goal.objects.get(title="Untergeschoben")
        self.assertEqual(goal.user, self.user_a)

    def test_goal_detail_shows_own_goal(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ziel von A")

    def test_goal_update_persists(self):
        response = self.client.post(
            reverse("core:goal_edit", args=[self.goal_a.pk]),
            {
                "title": "Ziel von A, ueberarbeitet",
                "description": "Jetzt mit Beschreibung",
                "status": "in-progress",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.goal_a.refresh_from_db()
        self.assertEqual(self.goal_a.title, "Ziel von A, ueberarbeitet")
        self.assertEqual(self.goal_a.status, "in-progress")

    def test_goal_delete_removes_goal(self):
        pk = self.goal_a.pk
        response = self.client.post(reverse("core:goal_delete", args=[pk]))

        self.assertRedirects(response, reverse("core:goal_list"))
        self.assertFalse(Goal.objects.filter(pk=pk).exists())

    def test_goal_delete_requires_post(self):
        response = self.client.get(reverse("core:goal_delete", args=[self.goal_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Goal.objects.filter(pk=self.goal_a.pk).exists())


class GoalStatusFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.geplant = Goal.objects.create(
            user=cls.user_a, title="A geplant", status="planned"
        )
        cls.laufend = Goal.objects.create(
            user=cls.user_a, title="A laufend", status="in-progress"
        )
        cls.fertig = Goal.objects.create(
            user=cls.user_a, title="A fertig", status="done"
        )
        cls.fremd_fertig = Goal.objects.create(
            user=cls.user_b, title="B fertig", status="done"
        )

    def setUp(self):
        self.client.force_login(self.user_a)

    def _titel(self, response):
        return sorted(g.title for g in response.context["object_list"])

    def test_filter_by_status_planned(self):
        response = self.client.get(reverse("core:goal_list"), {"status": "planned"})
        self.assertEqual(self._titel(response), ["A geplant"])

    def test_filter_by_status_in_progress(self):
        response = self.client.get(reverse("core:goal_list"), {"status": "in-progress"})
        self.assertEqual(self._titel(response), ["A laufend"])

    def test_filter_by_status_done(self):
        response = self.client.get(reverse("core:goal_list"), {"status": "done"})
        self.assertEqual(self._titel(response), ["A fertig"])

    def test_no_filter_returns_all_own_goals(self):
        response = self.client.get(reverse("core:goal_list"))
        self.assertEqual(self._titel(response), ["A fertig", "A geplant", "A laufend"])

    def test_invalid_status_value_returns_all(self):
        response = self.client.get(reverse("core:goal_list"), {"status": "unsinn"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._titel(response), ["A fertig", "A geplant", "A laufend"])

    def test_empty_status_value_returns_all(self):
        response = self.client.get(reverse("core:goal_list"), {"status": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._titel(response), ["A fertig", "A geplant", "A laufend"])

    def test_filter_does_not_leak_foreign_goals(self):
        response = self.client.get(reverse("core:goal_list"), {"status": "done"})

        self.assertNotIn(self.fremd_fertig, response.context["object_list"])
        self.assertNotContains(response, "B fertig")
