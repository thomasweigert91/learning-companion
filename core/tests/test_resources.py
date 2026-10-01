from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Goal, Resource

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
URL = "https://example.com/artikel"


class ResourceModellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")

    def test_resource_str_returns_title(self):
        resource = Resource.objects.create(
            goal=self.goal, url=URL, title="Django Doku"
        )
        self.assertEqual(str(resource), "Django Doku")

    def test_default_type_is_article(self):
        resource = Resource.objects.create(goal=self.goal, url=URL, title="Ohne Typ")
        self.assertEqual(resource.type, Resource.Type.ARTICLE)
        self.assertEqual(resource.type, "article")

    def test_all_four_types_are_valid(self):
        for wert in ("article", "video", "repo", "doc"):
            with self.subTest(type=wert):
                resource = Resource(
                    goal=self.goal, url=URL, title=f"Typ {wert}", type=wert
                )
                resource.full_clean()  # darf nicht werfen

    def test_invalid_type_rejected_by_full_clean(self):
        resource = Resource(
            goal=self.goal, url=URL, title="Podcast", type="podcast"
        )
        with self.assertRaises(ValidationError) as ctx:
            resource.full_clean()
        self.assertIn("type", ctx.exception.message_dict)

    def test_invalid_url_rejected_by_full_clean(self):
        resource = Resource(goal=self.goal, url="kein-link", title="Kaputt")
        with self.assertRaises(ValidationError) as ctx:
            resource.full_clean()
        self.assertIn("url", ctx.exception.message_dict)

    def test_deleting_goal_cascades_to_resources(self):
        Resource.objects.create(goal=self.goal, url=URL, title="Eins")
        Resource.objects.create(goal=self.goal, url=URL, title="Zwei")
        alte_id = self.goal.pk

        self.goal.delete()

        self.assertEqual(Resource.objects.filter(goal_id=alte_id).count(), 0)


class ResourceAnlegenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")
        cls.anderes_goal = Goal.objects.create(user=cls.user, title="Zweites Ziel")

    def setUp(self):
        self.client.force_login(self.user)

    def test_goal_detail_contains_resource_form(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("resource_form", response.context)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_create_resource_redirects_to_goal_detail(self):
        response = self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {"url": URL, "title": "Django Doku", "type": "doc"},
        )

        self.assertRedirects(
            response, reverse("core:goal_detail", args=[self.goal.pk])
        )
        resource = Resource.objects.get(title="Django Doku")
        self.assertEqual(resource.goal, self.goal)
        self.assertEqual(resource.type, "doc")

    def test_create_resource_appears_on_detail_page(self):
        self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {"url": URL, "title": "Sichtbare Ressource", "type": "article"},
        )

        response = self.client.get(reverse("core:goal_detail", args=[self.goal.pk]))
        self.assertContains(response, "Sichtbare Ressource")

    def test_create_resource_with_invalid_url_shows_errors(self):
        anzahl_vorher = Resource.objects.count()

        response = self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {"url": "kein-link", "title": "Kaputt", "type": "article"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("url", response.context["resource_form"].errors)
        self.assertEqual(Resource.objects.count(), anzahl_vorher)

    def test_create_resource_with_empty_title_shows_errors(self):
        anzahl_vorher = Resource.objects.count()

        response = self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {"url": URL, "title": "", "type": "article"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["resource_form"].errors)
        self.assertEqual(Resource.objects.count(), anzahl_vorher)

    def test_invalid_post_keeps_existing_resources_visible(self):
        Resource.objects.create(
            goal=self.goal, url=URL, title="Bereits vorhanden", type="repo"
        )

        response = self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {"url": "kein-link", "title": "Kaputt", "type": "article"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bereits vorhanden")

    def test_goal_field_in_post_is_ignored(self):
        # "goal" ist kein Formularfeld; massgeblich ist der PK aus der URL.
        self.client.post(
            reverse("core:resource_create", args=[self.goal.pk]),
            {
                "url": URL,
                "title": "Untergeschoben",
                "type": "article",
                "goal": self.anderes_goal.pk,
            },
        )

        resource = Resource.objects.get(title="Untergeschoben")
        self.assertEqual(resource.goal, self.goal)


class ResourceAnzeigeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")
        cls.leeres_goal = Goal.objects.create(user=cls.user, title="Ohne Ressourcen")

    def setUp(self):
        self.client.force_login(self.user)

    def test_resource_badge_class_matches_type(self):
        for wert in ("article", "video", "repo", "doc"):
            with self.subTest(type=wert):
                goal = Goal.objects.create(user=self.user, title=f"Ziel {wert}")
                Resource.objects.create(
                    goal=goal, url=URL, title=f"Ressource {wert}", type=wert
                )

                response = self.client.get(
                    reverse("core:goal_detail", args=[goal.pk])
                )
                self.assertContains(response, f"badge-{wert}")

    def test_resource_type_label_is_human_readable(self):
        Resource.objects.create(
            goal=self.goal, url=URL, title="Django Quellcode", type="repo"
        )

        response = self.client.get(reverse("core:goal_detail", args=[self.goal.pk]))

        self.assertContains(response, "Repository")

    def test_empty_resource_list_shows_hint(self):
        response = self.client.get(
            reverse("core:goal_detail", args=[self.leeres_goal.pk])
        )

        self.assertContains(response, "Noch keine Ressourcen")


class ResourceLoeschenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")

    def setUp(self):
        self.client.force_login(self.user)
        self.resource = Resource.objects.create(
            goal=self.goal, url=URL, title="Zu loeschen", type="video"
        )

    def test_delete_resource_removes_it_and_redirects(self):
        pk = self.resource.pk

        response = self.client.post(reverse("core:resource_delete", args=[pk]))

        self.assertRedirects(
            response, reverse("core:goal_detail", args=[self.goal.pk])
        )
        self.assertFalse(Resource.objects.filter(pk=pk).exists())

    def test_delete_resource_keeps_goal(self):
        self.client.post(reverse("core:resource_delete", args=[self.resource.pk]))

        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())

    def test_delete_requires_post(self):
        response = self.client.get(
            reverse("core:resource_delete", args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Resource.objects.filter(pk=self.resource.pk).exists())
