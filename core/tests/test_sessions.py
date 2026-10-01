import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Goal, LearningSession, Tag

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
DATUM = datetime.date(2026, 9, 15)


class LearningSessionModellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")

    def test_session_str_is_human_readable(self):
        session = LearningSession.objects.create(
            goal=self.goal, date=DATUM, duration=45
        )
        self.assertEqual(str(session), "Django lernen am 15.09.2026")

    def test_duration_zero_rejected(self):
        session = LearningSession(goal=self.goal, date=DATUM, duration=0)
        with self.assertRaises(ValidationError) as ctx:
            session.full_clean()
        self.assertIn("duration", ctx.exception.message_dict)

    def test_duration_negative_rejected(self):
        session = LearningSession(goal=self.goal, date=DATUM, duration=-30)
        with self.assertRaises(ValidationError) as ctx:
            session.full_clean()
        self.assertIn("duration", ctx.exception.message_dict)

    def test_duration_positive_accepted(self):
        session = LearningSession(goal=self.goal, date=DATUM, duration=1)
        session.full_clean()  # darf nicht werfen

    def test_deleting_goal_cascades_to_sessions(self):
        LearningSession.objects.create(goal=self.goal, date=DATUM, duration=45)
        LearningSession.objects.create(goal=self.goal, date=DATUM, duration=90)
        alte_id = self.goal.pk

        self.goal.delete()

        self.assertEqual(LearningSession.objects.filter(goal_id=alte_id).count(), 0)


class LearningSessionCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag_python = Tag.objects.create(name="Python")
        cls.tag_orm = Tag.objects.create(name="ORM")

        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.goal_a = Goal.objects.create(user=cls.user_a, title="Ziel von A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="Ziel von B")

        cls.session_a = LearningSession.objects.create(
            goal=cls.goal_a, date=DATUM, duration=60, notes="Notiz von A"
        )
        cls.session_b = LearningSession.objects.create(
            goal=cls.goal_b, date=DATUM, duration=30, notes="Notiz von B"
        )

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_session_list_shows_only_own_sessions(self):
        response = self.client.get(reverse("core:session_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.session_a, response.context["object_list"])
        self.assertNotIn(self.session_b, response.context["object_list"])
        self.assertContains(response, "Ziel von A")
        self.assertNotContains(response, "Ziel von B")

    def test_session_form_only_offers_own_goals(self):
        response = self.client.get(reverse("core:session_create"))

        auswahl = response.context["form"].fields["goal"].queryset
        self.assertIn(self.goal_a, auswahl)
        self.assertNotIn(self.goal_b, auswahl)

    def test_session_create_with_own_goal(self):
        response = self.client.post(
            reverse("core:session_create"),
            {
                "goal": self.goal_a.pk,
                "date": "2026-09-20",
                "duration": 75,
                "notes": "Neue Sitzung",
                "tags": [self.tag_python.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        session = LearningSession.objects.get(notes="Neue Sitzung")
        self.assertEqual(session.goal, self.goal_a)
        self.assertEqual(session.duration, 75)

    def test_session_create_with_foreign_goal_rejected(self):
        anzahl_vorher = LearningSession.objects.count()

        response = self.client.post(
            reverse("core:session_create"),
            {
                "goal": self.goal_b.pk,
                "date": "2026-09-20",
                "duration": 60,
                "notes": "Darf nicht entstehen",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("goal", response.context["form"].errors)
        self.assertEqual(LearningSession.objects.count(), anzahl_vorher)
        self.assertFalse(
            LearningSession.objects.filter(notes="Darf nicht entstehen").exists()
        )

    def test_session_create_with_invalid_duration_rejected(self):
        anzahl_vorher = LearningSession.objects.count()

        response = self.client.post(
            reverse("core:session_create"),
            {
                "goal": self.goal_a.pk,
                "date": "2026-09-20",
                "duration": 0,
                "notes": "Null Minuten",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("duration", response.context["form"].errors)
        self.assertEqual(LearningSession.objects.count(), anzahl_vorher)

    def test_session_detail_shows_own_session(self):
        response = self.client.get(
            reverse("core:session_detail", args=[self.session_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notiz von A")

    def test_session_update_persists(self):
        response = self.client.post(
            reverse("core:session_edit", args=[self.session_a.pk]),
            {
                "goal": self.goal_a.pk,
                "date": "2026-09-21",
                "duration": 120,
                "notes": "Ueberarbeitet",
                "tags": [self.tag_orm.pk],
            },
        )
        self.assertEqual(response.status_code, 302)

        self.session_a.refresh_from_db()
        self.assertEqual(self.session_a.duration, 120)
        self.assertEqual(self.session_a.notes, "Ueberarbeitet")
        self.assertEqual(self.session_a.date, datetime.date(2026, 9, 21))

    def test_session_tags_are_saved(self):
        self.client.post(
            reverse("core:session_edit", args=[self.session_a.pk]),
            {
                "goal": self.goal_a.pk,
                "date": "2026-09-15",
                "duration": 60,
                "notes": "Mit Tags",
                "tags": [self.tag_python.pk, self.tag_orm.pk],
            },
        )

        self.session_a.refresh_from_db()
        self.assertCountEqual(
            list(self.session_a.tags.values_list("name", flat=True)),
            ["Python", "ORM"],
        )

    def test_session_delete_removes_session(self):
        pk = self.session_a.pk
        response = self.client.post(reverse("core:session_delete", args=[pk]))

        self.assertRedirects(response, reverse("core:session_list"))
        self.assertFalse(LearningSession.objects.filter(pk=pk).exists())
