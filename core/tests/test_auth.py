from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"


class RegistrierungTests(TestCase):
    def test_register_creates_user_and_redirects(self):
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "neue_nutzerin",
                "email": "neue@example.com",
                "password1": PASSWORT,
                "password2": PASSWORT,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="neue_nutzerin").exists())

    def test_register_with_duplicate_username_fails(self):
        User.objects.create_user(username="belegt", password=PASSWORT)
        anzahl_vorher = User.objects.count()

        response = self.client.post(
            reverse("core:register"),
            {
                "username": "belegt",
                "password1": PASSWORT,
                "password2": PASSWORT,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), anzahl_vorher)

    def test_register_with_password_mismatch_fails(self):
        anzahl_vorher = User.objects.count()

        response = self.client.post(
            reverse("core:register"),
            {
                "username": "tippfehler",
                "password1": PASSWORT,
                "password2": PASSWORT + "-abweichend",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)
        self.assertEqual(User.objects.count(), anzahl_vorher)

    def test_password_is_hashed(self):
        self.client.post(
            reverse("core:register"),
            {
                "username": "gehasht",
                "password1": PASSWORT,
                "password2": PASSWORT,
            },
        )

        user = User.objects.get(username="gehasht")
        self.assertNotEqual(user.password, PASSWORT)
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertTrue(user.check_password(PASSWORT))


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)

    def test_login_success(self):
        response = self.client.post(
            reverse("core:login"),
            {"username": "lernende", "password": PASSWORT},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("core:login"),
            {"username": "lernende", "password": "falsches-passwort"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)

        # Django 5: LogoutView akzeptiert nur POST.
        self.client.post(reverse("core:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.get(reverse("core:profile_detail"))
        self.assertRedirects(
            response,
            f"{reverse('core:login')}?next={reverse('core:profile_detail')}",
        )
