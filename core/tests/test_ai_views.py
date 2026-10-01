import datetime
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import AIFeedback, Goal, LearningSession, Resource
from core.services import ai_service
from core.services.ai_service import AIServiceError

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
URL = "https://example.com/artikel"


class AIViewTestCase(TestCase):
    """Basis mit zwei Nutzern; der Mock wird in jeder Unterklasse erzwungen."""

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)

        cls.goal_a = Goal.objects.create(user=cls.user_a, title="Ziel von A")
        cls.goal_a2 = Goal.objects.create(user=cls.user_a, title="Zweites Ziel von A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="Ziel von B")

        LearningSession.objects.create(
            goal=cls.goal_a, date=datetime.date(2026, 9, 15), duration=60
        )
        Resource.objects.create(
            goal=cls.goal_a, url=URL, title="Django Doku", type="doc"
        )


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class KeinNetzwerkTests(AIViewTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_no_external_call_during_tests(self):
        """Jeder echte SDK-Kontakt laesst diesen Test scheitern."""

        def niemals(*args, **kwargs):
            self.fail("Es wurde ein echter OpenAI-Aufruf ausgeloest.")

        with patch("core.services.ai_service._call_openai", side_effect=niemals):
            self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))
            self.client.post(
                reverse("core:goal_ai_next_steps", args=[self.goal_a.pk])
            )


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class AktionenUndAnzeigeTests(AIViewTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_summary_action_redirects_to_goal_detail(self):
        response = self.client.post(
            reverse("core:goal_ai_summary", args=[self.goal_a.pk])
        )

        self.assertRedirects(
            response, reverse("core:goal_detail", args=[self.goal_a.pk])
        )

    def test_summary_result_visible_on_detail_page(self):
        self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))

        response = self.client.get(reverse("core:goal_detail", args=[self.goal_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("ai_summary", response.context)
        self.assertContains(response, "Fortschrittszusammenfassung")
        self.assertContains(response, "Ziel von A")

    def test_next_steps_action_redirects_and_shows_list(self):
        response = self.client.post(
            reverse("core:goal_ai_next_steps", args=[self.goal_a.pk])
        )
        self.assertRedirects(
            response, reverse("core:goal_detail", args=[self.goal_a.pk])
        )

        detail = self.client.get(reverse("core:goal_detail", args=[self.goal_a.pk]))
        schritte = detail.context["ai_next_steps"].steps

        self.assertGreaterEqual(len(schritte), 2)
        self.assertLessEqual(len(schritte), 3)
        self.assertContains(detail, "Naechste Lernschritte")

    def test_actions_not_triggered_by_get(self):
        for name in ("core:goal_ai_summary", "core:goal_ai_next_steps"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=[self.goal_a.pk]))

                self.assertEqual(response.status_code, 405)

        self.assertEqual(AIFeedback.objects.count(), 0)

    def test_no_result_block_before_first_use(self):
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_a.pk]))

        self.assertNotIn("ai_summary", response.context)
        self.assertNotIn("ai_next_steps", response.context)
        self.assertNotContains(response, "Fortschrittszusammenfassung")
        self.assertNotContains(response, "Naechste Lernschritte")

    def test_result_of_other_goal_not_shown(self):
        self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))

        # Dasselbe Konto, anderes Goal: das Ergebnis darf dort nicht auftauchen.
        response = self.client.get(reverse("core:goal_detail", args=[self.goal_a2.pk]))

        self.assertNotIn("ai_summary", response.context)
        self.assertNotContains(response, "Fortschrittszusammenfassung")

    def test_results_are_persisted_per_type(self):
        # Feature 8 kehrt den frueheren Vertrag (nur Session, nie DB) bewusst um.
        self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))
        self.client.post(reverse("core:goal_ai_next_steps", args=[self.goal_a.pk]))

        self.assertEqual(
            sorted(
                AIFeedback.objects.filter(goal=self.goal_a).values_list(
                    "feedback_type", flat=True
                )
            ),
            ["next_steps", "summary"],
        )
        # Gespeichert wird neben dem Goal, das Goal selbst bleibt unveraendert.
        self.goal_a.refresh_from_db()
        self.assertEqual(self.goal_a.title, "Ziel von A")


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class FehlerpfadTests(AIViewTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def _poste_mit_fehler(self, ziel, meldung):
        with patch(
            f"core.services.ai_service.{ziel}",
            side_effect=AIServiceError(meldung),
        ):
            return self.client.post(
                reverse("core:goal_ai_summary", args=[self.goal_a.pk]), follow=True
            )

    def test_timeout_shows_message_and_redirects(self):
        response = self._poste_mit_fehler(
            "generate_summary", "Die KI-Antwort hat zu lange gedauert."
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "zu lange gedauert")

    def test_rate_limit_shows_message(self):
        response = self._poste_mit_fehler(
            "generate_summary", "Das Anfragelimit der KI ist erreicht."
        )

        self.assertContains(response, "Anfragelimit")

    def test_unexpected_error_shows_message(self):
        response = self._poste_mit_fehler(
            "generate_summary", "Die KI-Funktion ist momentan nicht verfuegbar."
        )

        self.assertContains(response, "nicht verfuegbar")

    def test_failed_action_does_not_return_500(self):
        with patch(
            "core.services.ai_service.generate_summary",
            side_effect=AIServiceError("Fehlgeschlagen"),
        ):
            response = self.client.post(
                reverse("core:goal_ai_summary", args=[self.goal_a.pk])
            )

        self.assertEqual(response.status_code, 302)

    def test_failed_action_leaves_no_result(self):
        with patch(
            "core.services.ai_service.suggest_next_steps",
            side_effect=AIServiceError("Fehlgeschlagen"),
        ):
            self.client.post(
                reverse("core:goal_ai_next_steps", args=[self.goal_a.pk])
            )

        self.assertEqual(AIFeedback.objects.count(), 0)


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class ScopingTests(AIViewTestCase):
    def test_ai_actions_require_login(self):
        for name in ("core:goal_ai_summary", "core:goal_ai_next_steps"):
            with self.subTest(route=name):
                url = reverse(name, args=[self.goal_a.pk])

                response = self.client.post(url)

                self.assertRedirects(
                    response, f"{reverse('core:login')}?next={url}"
                )

    def test_ai_actions_on_foreign_goal_return_404(self):
        self.client.force_login(self.user_a)

        for name in ("core:goal_ai_summary", "core:goal_ai_next_steps"):
            with self.subTest(route=name):
                response = self.client.post(reverse(name, args=[self.goal_b.pk]))

                self.assertEqual(response.status_code, 404)

    def test_foreign_goal_action_does_not_call_service(self):
        """Der 404 muss fallen, bevor ueberhaupt ein API-Kontakt entsteht."""
        self.client.force_login(self.user_a)

        with patch("core.services.ai_service.generate_summary") as doppel:
            self.client.post(reverse("core:goal_ai_summary", args=[self.goal_b.pk]))

        doppel.assert_not_called()

    def test_own_goal_actions_work(self):
        # Gegenprobe: ohne sie waeren die 404-Tests trivial erfuellbar.
        self.client.force_login(self.user_a)

        zusammenfassung = self.client.post(
            reverse("core:goal_ai_summary", args=[self.goal_a.pk])
        )
        schritte = self.client.post(
            reverse("core:goal_ai_next_steps", args=[self.goal_a.pk])
        )

        self.assertEqual(zusammenfassung.status_code, 302)
        self.assertEqual(schritte.status_code, 302)
        self.assertEqual(
            AIFeedback.objects.filter(goal=self.goal_a, feedback_type="summary").count(), 1
        )
        self.assertEqual(
            AIFeedback.objects.filter(goal=self.goal_a, feedback_type="next_steps").count(),
            1,
        )


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="", OPENAI_TIMEOUT_SECONDS=20)
class LadezustandTests(AIViewTestCase):
    """Markup-Vertrag fuer das Ladezustands-Script der Detailseite.

    Das Verhalten selbst laeuft im Browser; hier wird gesichert, dass alles
    vorhanden ist, worauf das Script zugreift.
    """

    def setUp(self):
        self.client.force_login(self.user_a)
        self.html = self.client.get(
            reverse("core:goal_detail", args=[self.goal_a.pk])
        ).content.decode()

    def test_beide_formulare_markiert_mit_ladetext(self):
        formulare = re.findall(r"<form [^>]*data-ki-aktion>", self.html)
        self.assertEqual(len(formulare), 2)
        self.assertIn('data-ladetext="Generiere Zusammenfassung..."', self.html)
        self.assertIn('data-ladetext="Ermittle nächste Schritte..."', self.html)

    def test_live_region_fuer_screenreader(self):
        self.assertIn('<p class="visually-hidden" role="status" id="ki-status"></p>', self.html)

    def test_freigabefrist_aus_timeout_und_wiederholungen(self):
        # 20 s x 2 Versuche + 10 s Wartezeit fuer die eine Wiederholung.
        self.assertIn('data-freigabe-ms="50000"', self.html)

    def test_script_mit_spinner_und_doppelklick_schutz(self):
        script = self.html[self.html.index("Ladezustand der beiden KI-Aktionen") :]
        self.assertIn('"spinner-border spinner-border-sm me-2"', script)
        self.assertIn('setAttribute("aria-hidden", "true")', script)
        self.assertIn("event.preventDefault()", script)
        self.assertIn("pageshow", script)
        # Das Script steht nach dem Bootstrap-Bundle.
        self.assertLess(
            self.html.index("bootstrap.bundle.min.js"),
            self.html.index("Ladezustand der beiden"),
        )

    def test_script_nur_auf_der_detailseite(self):
        liste = self.client.get(reverse("core:goal_list")).content.decode()
        self.assertNotIn("data-ki-aktion", liste)
        self.assertNotIn("Ladezustand der beiden KI-Aktionen", liste)


class MaxRequestSecondsTests(TestCase):
    @override_settings(OPENAI_TIMEOUT_SECONDS=5)
    def test_frist_folgt_dem_timeout(self):
        self.assertEqual(ai_service.max_request_seconds(), 5 * 2 + 10)
