from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Profile, Tag

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"


class ProfilErzeugungTests(TestCase):
    def test_profile_created_automatically_on_user_creation(self):
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "frischling",
                "password1": PASSWORT,
                "password2": PASSWORT,
            },
        )
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username="frischling")
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_profile_str_is_human_readable(self):
        user = User.objects.create_user(username="ohne_namen", password=PASSWORT)
        profil = user.profile

        # Ohne gesetzten Namen faellt __str__ auf den Usernamen zurueck.
        self.assertEqual(str(profil), "ohne_namen")

        profil.name = "Alex Beispiel"
        profil.save()
        self.assertEqual(str(profil), "Alex Beispiel")
        self.assertNotIn("Profile object", str(profil))


class ProfilAnzeigeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.python_tag = Tag.objects.create(name="Python")
        cls.ml_tag = Tag.objects.create(name="Machine Learning")
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.profil = cls.user.profile
        cls.profil.name = "Alex Beispiel"
        cls.profil.cohort = "Kohorte 2026-A"
        cls.profil.save()
        cls.profil.focus_areas.add(cls.python_tag)

    def setUp(self):
        self.client.force_login(self.user)

    def test_profile_detail_shows_own_data(self):
        response = self.client.get(reverse("core:profile_detail"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex Beispiel")
        self.assertContains(response, "Kohorte 2026-A")
        self.assertContains(response, "Python")

    def test_profile_update_persists(self):
        response = self.client.post(
            reverse("core:profile_edit"),
            {
                "name": "Alex Geaendert",
                "cohort": "Kohorte 2026-B",
                "focus_areas": [self.python_tag.pk, self.ml_tag.pk],
            },
        )
        self.assertRedirects(response, reverse("core:profile_detail"))

        self.profil.refresh_from_db()
        self.assertEqual(self.profil.name, "Alex Geaendert")
        self.assertEqual(self.profil.cohort, "Kohorte 2026-B")
        self.assertCountEqual(
            list(self.profil.focus_areas.values_list("name", flat=True)),
            ["Python", "Machine Learning"],
        )
