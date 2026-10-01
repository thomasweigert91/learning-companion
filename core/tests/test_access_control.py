from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Tag

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"


class AnonymerZugriffTests(TestCase):
    def test_anonymous_redirected_from_profile_detail(self):
        response = self.client.get(reverse("core:profile_detail"))
        self.assertRedirects(
            response,
            f"{reverse('core:login')}?next={reverse('core:profile_detail')}",
        )

    def test_anonymous_redirected_from_profile_edit(self):
        response = self.client.get(reverse("core:profile_edit"))
        self.assertRedirects(
            response,
            f"{reverse('core:login')}?next={reverse('core:profile_edit')}",
        )


class FremdzugriffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="Python")

        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.profil_a = cls.user_a.profile
        cls.profil_a.name = "Alex A"
        cls.profil_a.cohort = "Kohorte A"
        cls.profil_a.save()

        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)
        cls.profil_b = cls.user_b.profile
        cls.profil_b.name = "Bea B"
        cls.profil_b.cohort = "Kohorte B"
        cls.profil_b.save()

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_user_cannot_access_foreign_profile_detail(self):
        response = self.client.get(
            reverse("core:profile_detail_pk", args=[self.profil_b.pk])
        )

        self.assertIn(response.status_code, (403, 404))
        self.assertNotContains(response, "Bea B", status_code=response.status_code)

    def test_user_cannot_edit_foreign_profile(self):
        response = self.client.post(
            reverse("core:profile_edit_pk", args=[self.profil_b.pk]),
            {
                "name": "Uebernommen durch A",
                "cohort": "Gekapert",
                "focus_areas": [self.tag.pk],
            },
        )

        self.assertIn(response.status_code, (403, 404))

        # Der Schreibpfad muss ebenfalls blockiert sein, nicht nur die Anzeige.
        self.profil_b.refresh_from_db()
        self.assertEqual(self.profil_b.name, "Bea B")
        self.assertEqual(self.profil_b.cohort, "Kohorte B")

    def test_profile_edit_updates_only_own_profile(self):
        response = self.client.post(
            reverse("core:profile_edit"),
            {
                "name": "Alex Neu",
                "cohort": "Kohorte A2",
                "focus_areas": [self.tag.pk],
            },
        )
        self.assertRedirects(response, reverse("core:profile_detail"))

        self.profil_a.refresh_from_db()
        self.assertEqual(self.profil_a.name, "Alex Neu")

        self.profil_b.refresh_from_db()
        self.assertEqual(self.profil_b.name, "Bea B")
        self.assertEqual(self.profil_b.cohort, "Kohorte B")

    def test_own_pk_route_still_works(self):
        response = self.client.get(
            reverse("core:profile_detail_pk", args=[self.profil_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex A")
