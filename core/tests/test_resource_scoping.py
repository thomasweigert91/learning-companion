"""Mandantentrennung fuer Ressourcen: A darf nicht an die Daten von B."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Goal, Resource

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
URL = "https://example.com/artikel"


class ZweiNutzerMitRessourcen(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.goal_a = Goal.objects.create(user=cls.user_a, title="Ziel von A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="Ziel von B")

        cls.resource_a = Resource.objects.create(
            goal=cls.goal_a, url=URL, title="Ressource von A", type="article"
        )
        cls.resource_b = Resource.objects.create(
            goal=cls.goal_b, url=URL, title="Ressource von B", type="video"
        )


class AnonymerZugriffTests(ZweiNutzerMitRessourcen):
    def test_resource_create_requires_login(self):
        url = reverse("core:resource_create", args=[self.goal_a.pk])

        response = self.client.post(
            url, {"url": URL, "title": "Anonym", "type": "article"}
        )

        self.assertRedirects(response, f"{reverse('core:login')}?next={url}")
        self.assertFalse(Resource.objects.filter(title="Anonym").exists())

    def test_resource_delete_requires_login(self):
        url = reverse("core:resource_delete", args=[self.resource_a.pk])

        response = self.client.post(url)

        self.assertRedirects(response, f"{reverse('core:login')}?next={url}")
        self.assertTrue(Resource.objects.filter(pk=self.resource_a.pk).exists())


class FremdzugriffTests(ZweiNutzerMitRessourcen):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_cannot_add_resource_to_foreign_goal(self):
        anzahl_vorher = Resource.objects.count()

        response = self.client.post(
            reverse("core:resource_create", args=[self.goal_b.pk]),
            {"url": URL, "title": "Untergeschoben bei B", "type": "article"},
        )

        # 404 allein genuegt nicht -- es muss auch nichts geschrieben worden sein.
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Resource.objects.count(), anzahl_vorher)
        self.assertFalse(
            Resource.objects.filter(title="Untergeschoben bei B").exists()
        )

    def test_cannot_delete_foreign_resource(self):
        response = self.client.post(
            reverse("core:resource_delete", args=[self.resource_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Resource.objects.filter(pk=self.resource_b.pk).exists())

    def test_cannot_get_delete_page_of_foreign_resource(self):
        response = self.client.get(
            reverse("core:resource_delete", args=[self.resource_b.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Ressource von B", status_code=404)

    def test_foreign_goal_detail_still_404(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_b.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Ressource von B", status_code=404)

    def test_foreign_resources_not_on_own_goal_detail(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ressource von A")
        self.assertNotContains(response, "Ressource von B")


class GegenprobeTests(ZweiNutzerMitRessourcen):
    """Ohne diese Gegenprobe waeren die 404-Tests auch durch eine global
    kaputte View trivial erfuellt."""

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_own_resource_create_and_delete_work(self):
        anlegen = self.client.post(
            reverse("core:resource_create", args=[self.goal_a.pk]),
            {"url": URL, "title": "Eigene Ressource", "type": "repo"},
        )
        self.assertRedirects(
            anlegen, reverse("core:goal_detail", args=[self.goal_a.pk])
        )

        neue = Resource.objects.get(title="Eigene Ressource")
        self.assertEqual(neue.goal, self.goal_a)

        loeschen = self.client.post(
            reverse("core:resource_delete", args=[neue.pk])
        )
        self.assertRedirects(
            loeschen, reverse("core:goal_detail", args=[self.goal_a.pk])
        )
        self.assertFalse(Resource.objects.filter(pk=neue.pk).exists())
