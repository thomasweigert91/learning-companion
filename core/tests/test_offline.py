"""Die Testsuite darf nie das echte OpenAI-Konto erreichen -- auch nicht mit .env."""

from django.conf import settings
from django.test import SimpleTestCase

from core.services import ai_service


class OfflineTestRunnerTests(SimpleTestCase):
    def test_testlauf_erzwingt_mock_modus(self):
        # Bewusst ohne @override_settings: geprueft wird der globale Schutz.
        self.assertTrue(settings.AI_MOCK_MODE)
        self.assertEqual(settings.OPENAI_API_KEY, "")
        self.assertTrue(ai_service.is_mock_mode())
