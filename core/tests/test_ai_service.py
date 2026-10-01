import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Goal, LearningSession, Resource
from core.services import ai_service

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
URL = "https://example.com/artikel"

# Bewusst ohne das echte Schluessel-Praefix, damit die Repository-Suche nach
# einem Schluessel-Literal auch in den Testdaten ohne Treffer bleibt.
TEST_SCHLUESSEL = "test-schluessel-platzhalter"


class MockModusTests(TestCase):
    @override_settings(AI_MOCK_MODE=False, OPENAI_API_KEY="")
    def test_mock_mode_active_without_api_key(self):
        # Ohne Schluessel muss der Mock greifen, auch wenn er nicht gesetzt ist.
        self.assertTrue(ai_service.is_mock_mode())

    @override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY=TEST_SCHLUESSEL)
    def test_mock_mode_active_when_explicitly_enabled(self):
        self.assertTrue(ai_service.is_mock_mode())

    @override_settings(AI_MOCK_MODE=False, OPENAI_API_KEY=TEST_SCHLUESSEL)
    def test_mock_mode_inactive_with_key_and_flag_off(self):
        self.assertFalse(ai_service.is_mock_mode())


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class MockErgebnisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")
        LearningSession.objects.create(
            goal=cls.goal, date=datetime.date(2026, 9, 15), duration=60
        )
        LearningSession.objects.create(
            goal=cls.goal, date=datetime.date(2026, 9, 16), duration=30
        )
        Resource.objects.create(goal=cls.goal, url=URL, title="Django Doku", type="doc")

    def test_generate_summary_returns_text_in_mock_mode(self):
        ergebnis = ai_service.generate_summary(self.goal)

        self.assertIsInstance(ergebnis, str)
        self.assertTrue(ergebnis.strip())
        self.assertIn("Django lernen", ergebnis)

    def test_suggest_next_steps_returns_two_to_three_items(self):
        schritte = ai_service.suggest_next_steps(self.goal)

        self.assertIsInstance(schritte, list)
        self.assertGreaterEqual(len(schritte), ai_service.MIN_STEPS)
        self.assertLessEqual(len(schritte), ai_service.MAX_STEPS)
        for schritt in schritte:
            self.assertTrue(schritt.strip())

    def test_service_does_not_touch_database(self):
        vorher = (
            Goal.objects.count(),
            LearningSession.objects.count(),
            Resource.objects.count(),
        )

        ai_service.generate_summary(self.goal)
        ai_service.suggest_next_steps(self.goal)

        nachher = (
            Goal.objects.count(),
            LearningSession.objects.count(),
            Resource.objects.count(),
        )
        self.assertEqual(vorher, nachher)


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class PromptInhaltTests(TestCase):
    """Der sicherheitsrelevante Teil: nur eigene Daten im Prompt."""

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.goal_a = Goal.objects.create(user=cls.user_a, title="ZIEL-MARKER-A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="ZIEL-MARKER-B")

        LearningSession.objects.create(
            goal=cls.goal_a,
            date=datetime.date(2026, 9, 15),
            duration=60,
            notes="SESSION-MARKER-A",
        )
        LearningSession.objects.create(
            goal=cls.goal_b,
            date=datetime.date(2026, 9, 15),
            duration=60,
            notes="SESSION-MARKER-B",
        )

        Resource.objects.create(
            goal=cls.goal_a, url=URL, title="RESSOURCE-MARKER-A", type="repo"
        )
        Resource.objects.create(
            goal=cls.goal_b, url=URL, title="RESSOURCE-MARKER-B", type="repo"
        )

    def test_summary_prompt_contains_only_own_goal_data(self):
        prompt = ai_service._build_summary_prompt(self.goal_a)

        self.assertIn("ZIEL-MARKER-A", prompt)
        self.assertIn("SESSION-MARKER-A", prompt)
        self.assertIn("RESSOURCE-MARKER-A", prompt)

        self.assertNotIn("ZIEL-MARKER-B", prompt)
        self.assertNotIn("SESSION-MARKER-B", prompt)
        self.assertNotIn("RESSOURCE-MARKER-B", prompt)

    def test_next_steps_prompt_contains_only_own_goal_data(self):
        prompt = ai_service._build_next_steps_prompt(self.goal_a)

        self.assertIn("ZIEL-MARKER-A", prompt)
        self.assertNotIn("ZIEL-MARKER-B", prompt)
        self.assertNotIn("SESSION-MARKER-B", prompt)

    def test_prompt_limits_number_of_sessions(self):
        for tag in range(1, 26):
            LearningSession.objects.create(
                goal=self.goal_a,
                date=datetime.date(2026, 10, 1) + datetime.timedelta(days=tag),
                duration=30,
                notes=f"EXTRA-{tag}",
            )

        prompt = ai_service._build_summary_prompt(self.goal_a)

        # Jede Sitzungszeile beginnt mit "- " und einem Datum.
        sitzungszeilen = [
            zeile
            for zeile in prompt.splitlines()
            if zeile.startswith("- ") and "Minuten" in zeile
        ]
        self.assertLessEqual(len(sitzungszeilen), ai_service.MAX_SESSIONS)

    def test_prompt_contains_resources(self):
        prompt = ai_service._build_summary_prompt(self.goal_a)

        self.assertIn("RESSOURCE-MARKER-A", prompt)
        self.assertIn("Repository", prompt)


@override_settings(AI_MOCK_MODE=False, OPENAI_API_KEY=TEST_SCHLUESSEL)
class FehlerUebersetzungTests(TestCase):
    """Mock bewusst abgeschaltet; das SDK wird gepatcht, nie echt aufgerufen."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="lernende", password=PASSWORT)
        cls.goal = Goal.objects.create(user=cls.user, title="Django lernen")

    def _patche_sdk_mit(self, exception):
        """Ersetzt die SDK-Methode durch eine, die den gewuenschten Fehler wirft."""
        return patch(
            "core.services.ai_service.OpenAI",
            side_effect=None,
            **{"return_value.chat.completions.create.side_effect": exception},
        )

    # assertLogs belegt zugleich, dass der Fehler fuer den Betrieb protokolliert
    # wird -- er wird dem Nutzer gegenueber verschluckt, darf aber nicht
    # spurlos verschwinden. Nebeneffekt: der Testoutput bleibt sauber.
    LOGGER = "core.services.ai_service"

    def test_timeout_is_translated_to_service_error(self):
        from openai import APITimeoutError

        fehler = APITimeoutError(request=None)
        with self._patche_sdk_mit(fehler):
            with self.assertLogs(self.LOGGER, level="WARNING"):
                with self.assertRaises(ai_service.AIServiceError):
                    ai_service.generate_summary(self.goal)

    def test_rate_limit_is_translated_to_service_error(self):
        from openai import RateLimitError

        fehler = RateLimitError("rate limit", response=_FakeResponse(429), body=None)
        with self._patche_sdk_mit(fehler):
            with self.assertLogs(self.LOGGER, level="WARNING"):
                with self.assertRaises(ai_service.AIServiceError):
                    ai_service.suggest_next_steps(self.goal)

    def test_unexpected_exception_is_translated_to_service_error(self):
        with self._patche_sdk_mit(RuntimeError("irgendwas ging schief")):
            with self.assertLogs(self.LOGGER, level="ERROR"):
                with self.assertRaises(ai_service.AIServiceError):
                    ai_service.generate_summary(self.goal)

    def test_error_message_does_not_leak_internals(self):
        # Zusammengesetzt, damit das Praefix nicht als Literal im Repository steht.
        praefix = "sk" + "-"
        geheim = f"{praefix}streng-geheimer-schluessel"

        with self._patche_sdk_mit(RuntimeError(f"Fehler mit {geheim} im Text")):
            with self.assertLogs(self.LOGGER, level="ERROR"):
                with self.assertRaises(ai_service.AIServiceError) as ctx:
                    ai_service.generate_summary(self.goal)

        meldung = str(ctx.exception)
        self.assertNotIn(praefix, meldung)
        self.assertNotIn(geheim, meldung)
        self.assertNotIn("Traceback", meldung)
        self.assertNotIn("irgendwas ging schief", meldung)

    def test_empty_response_raises_service_error(self):
        # Liefert das Modell keine verwertbaren Zeilen, darf das kein 500er werden.
        with patch(
            "core.services.ai_service._call_openai", return_value="   \n  \n "
        ):
            with self.assertRaises(ai_service.AIServiceError):
                ai_service.suggest_next_steps(self.goal)


class _FakeResponse:
    """Minimales Response-Double fuer die SDK-Fehlerkonstruktoren."""

    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}
        self.request = None
