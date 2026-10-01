"""Persistente KI-Historie: Modell, Speichern, Anzeige, Loeschen, Scoping."""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import AIFeedback, Goal
from core.services.ai_service import AIServiceError

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
SUMMARY = AIFeedback.FeedbackType.SUMMARY
NEXT_STEPS = AIFeedback.FeedbackType.NEXT_STEPS


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class AIFeedbackTestCase(TestCase):
    """Zwei Nutzer; A hat zwei Goals, damit Goal-uebergreifende Fehler auffallen."""

    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)
        cls.goal_a = Goal.objects.create(user=cls.user_a, title="Ziel von A")
        cls.goal_a2 = Goal.objects.create(user=cls.user_a, title="Zweites Ziel von A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="Ziel von B")

    def setUp(self):
        self.client.force_login(self.user_a)

    def eintrag(self, goal, typ=SUMMARY, content="Inhalt", minuten_alt=None):
        feedback = AIFeedback.objects.create(goal=goal, feedback_type=typ, content=content)
        if minuten_alt is not None:
            # auto_now_add laesst sich beim Anlegen nicht ueberschreiben.
            AIFeedback.objects.filter(pk=feedback.pk).update(
                created_at=timezone.now() - datetime.timedelta(minutes=minuten_alt)
            )
            feedback.refresh_from_db()
        return feedback

    def detail(self, goal=None):
        response = self.client.get(reverse("core:goal_detail", args=[(goal or self.goal_a).pk]))
        self.assertEqual(response.status_code, 200)
        return response


class ModellTests(AIFeedbackTestCase):
    def test_sortierung_neueste_zuerst(self):
        alt = self.eintrag(self.goal_a, content="alt", minuten_alt=60)
        neu = self.eintrag(self.goal_a, content="neu", minuten_alt=1)
        self.assertEqual(list(self.goal_a.ai_feedbacks.all()), [neu, alt])

    def test_gleicher_zeitstempel_nach_pk(self):
        erster = self.eintrag(self.goal_a, content="erster")
        zweiter = self.eintrag(self.goal_a, content="zweiter")
        AIFeedback.objects.update(created_at=timezone.now())
        self.assertEqual(list(self.goal_a.ai_feedbacks.all()), [zweiter, erster])

    def test_steps_aus_zeilen(self):
        feedback = self.eintrag(
            self.goal_a, NEXT_STEPS, "Erster Schritt\n\n  Zweiter Schritt  \n"
        )
        self.assertEqual(feedback.steps, ["Erster Schritt", "Zweiter Schritt"])

    def test_cascade_beim_goal_loeschen(self):
        self.eintrag(self.goal_a)
        self.eintrag(self.goal_a, NEXT_STEPS)
        self.goal_a.delete()
        self.assertEqual(AIFeedback.objects.count(), 0)


class SpeichernTests(AIFeedbackTestCase):
    def test_summary_wird_gespeichert(self):
        with patch("core.services.ai_service.generate_summary", return_value="Gute Fortschritte."):
            self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))

        feedback = AIFeedback.objects.get()
        self.assertEqual(feedback.goal, self.goal_a)
        self.assertEqual(feedback.feedback_type, SUMMARY)
        self.assertEqual(feedback.content, "Gute Fortschritte.")

    def test_next_steps_zeilenweise_gespeichert(self):
        schritte = ["Kapitel 3 lesen", "Uebung 2 loesen", "Notizen ergaenzen"]
        with patch("core.services.ai_service.suggest_next_steps", return_value=schritte):
            self.client.post(reverse("core:goal_ai_next_steps", args=[self.goal_a.pk]))

        feedback = AIFeedback.objects.get()
        self.assertEqual(feedback.feedback_type, NEXT_STEPS)
        self.assertEqual(feedback.steps, schritte)

    def test_jede_aktion_ein_neuer_eintrag(self):
        """Historie statt Ueberschreiben."""
        url = reverse("core:goal_ai_summary", args=[self.goal_a.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(self.goal_a.ai_feedbacks.count(), 2)

    def test_fehler_speichert_nichts(self):
        for name, funktion in (
            ("core:goal_ai_summary", "generate_summary"),
            ("core:goal_ai_next_steps", "suggest_next_steps"),
        ):
            with self.subTest(route=name), patch(
                f"core.services.ai_service.{funktion}",
                side_effect=AIServiceError("Fehlgeschlagen"),
            ):
                self.client.post(reverse(name, args=[self.goal_a.pk]))
        self.assertEqual(AIFeedback.objects.count(), 0)

    @override_settings(AI_MOCK_MODE=False, OPENAI_API_KEY="test-schluessel-platzhalter")
    def test_echter_pfad_speichert_modellantwort(self):
        """Mock aus, SDK-Aufruf gepatcht: gespeichert wird die (bereinigte) Modellantwort."""
        with patch(
            "core.services.ai_service._call_openai", return_value="  Antwort des Modells  "
        ) as aufruf:
            self.client.post(reverse("core:goal_ai_summary", args=[self.goal_a.pk]))

        aufruf.assert_called_once()
        self.assertEqual(AIFeedback.objects.get().content, "Antwort des Modells")


class AnzeigeTests(AIFeedbackTestCase):
    def test_timeline_zeigt_alle_eintraege(self):
        alt = self.eintrag(self.goal_a, SUMMARY, "Aeltere Zusammenfassung", minuten_alt=90)
        self.eintrag(self.goal_a, NEXT_STEPS, "Schritt Alpha\nSchritt Beta", minuten_alt=5)

        html = self.detail().content.decode()
        verlauf = html[html.index('id="ki-verlauf"') :]

        self.assertIn("Aeltere Zusammenfassung", verlauf)
        self.assertIn("<li class=\"mb-1\">Schritt Alpha</li>", verlauf)
        # date:'c' gibt in der lokalen Zeitzone aus (TIME_ZONE), created_at ist UTC.
        self.assertIn(f'datetime="{timezone.localtime(alt.created_at).isoformat()}"', verlauf)
        self.assertIn("Zusammenfassung</span>", verlauf)
        self.assertIn("Naechste Schritte</span>", verlauf)
        # Neueste zuerst.
        self.assertLess(verlauf.index("Schritt Alpha"), verlauf.index("Aeltere Zusammenfassung"))

    def test_leerzustand(self):
        response = self.detail()
        self.assertContains(response, "Noch keine KI-Ergebnisse gespeichert.")
        self.assertNotContains(response, "Alle zuruecksetzen")

    def test_neuestes_ergebnis_in_ki_card(self):
        self.eintrag(self.goal_a, SUMMARY, "Alte Einschaetzung", minuten_alt=120)
        neu = self.eintrag(self.goal_a, SUMMARY, "Neue Einschaetzung", minuten_alt=1)

        response = self.detail()

        self.assertEqual(response.context["ai_summary"], neu)
        html = response.content.decode()
        karte = html[html.index('class="card-body border-top ai-summary"') :]
        karte = karte[: karte.index("</div>")]
        self.assertIn("Neue Einschaetzung", karte)
        self.assertNotIn("Alte Einschaetzung", karte)

    def test_abfragen_unabhaengig_von_eintragszahl(self):
        def anzahl_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.detail()
            return len(ctx.captured_queries)

        self.eintrag(self.goal_a, SUMMARY)
        self.eintrag(self.goal_a, NEXT_STEPS, "a\nb")
        bei_zwei = anzahl_queries()

        for _ in range(3):
            self.eintrag(self.goal_a, SUMMARY)
            self.eintrag(self.goal_a, NEXT_STEPS, "a\nb")
        bei_acht = anzahl_queries()

        self.assertEqual(bei_zwei, bei_acht)

    def test_eintraege_anderer_goals_unsichtbar(self):
        self.eintrag(self.goal_a, SUMMARY, "Nur fuer Goal A")
        response = self.detail(self.goal_a2)
        self.assertNotContains(response, "Nur fuer Goal A")
        self.assertNotIn("ai_summary", response.context)


class LoeschenTests(AIFeedbackTestCase):
    def test_einzelnen_eintrag_loeschen(self):
        weg = self.eintrag(self.goal_a, content="weg")
        bleibt = self.eintrag(self.goal_a, content="bleibt")

        response = self.client.post(reverse("core:ai_feedback_delete", args=[weg.pk]))

        self.assertRedirects(
            response,
            reverse("core:goal_detail", args=[self.goal_a.pk]) + "#ki-verlauf",
            fetch_redirect_response=False,
        )
        self.assertEqual(list(AIFeedback.objects.all()), [bleibt])

    def test_meldung_erscheint_im_verlauf_statt_oben(self):
        """Nach dem Redirect auf #ki-verlauf laege eine Meldung oben ausser Sicht."""
        feedback = self.eintrag(self.goal_a)

        response = self.client.post(
            reverse("core:ai_feedback_delete", args=[feedback.pk]), follow=True
        )

        html = response.content.decode()
        self.assertEqual(html.count("Der KI-Eintrag wurde geloescht."), 1)
        self.assertGreater(
            html.index("Der KI-Eintrag wurde geloescht."), html.index('id="ki-verlauf"')
        )

    def test_einzel_loeschen_nicht_per_get(self):
        feedback = self.eintrag(self.goal_a)
        response = self.client.get(reverse("core:ai_feedback_delete", args=[feedback.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(AIFeedback.objects.filter(pk=feedback.pk).exists())

    def test_alle_zuruecksetzen_bestaetigung(self):
        self.eintrag(self.goal_a)
        self.eintrag(self.goal_a, NEXT_STEPS)

        response = self.client.get(
            reverse("core:goal_ai_history_clear", args=[self.goal_a.pk])
        )

        self.assertContains(response, "Sollen alle 2 KI-Eintraege")
        self.assertEqual(AIFeedback.objects.count(), 2)

    def test_alle_zuruecksetzen_betrifft_nur_dieses_goal(self):
        self.eintrag(self.goal_a)
        self.eintrag(self.goal_a, NEXT_STEPS)
        anderes = self.eintrag(self.goal_a2)

        response = self.client.post(
            reverse("core:goal_ai_history_clear", args=[self.goal_a.pk]), follow=True
        )

        self.assertContains(response, "2 Eintraege geloescht")
        self.assertEqual(list(AIFeedback.objects.all()), [anderes])


class ScopingTests(AIFeedbackTestCase):
    def test_login_pflicht(self):
        feedback = self.eintrag(self.goal_a)
        self.client.logout()

        for url in (
            reverse("core:ai_feedback_delete", args=[feedback.pk]),
            reverse("core:goal_ai_history_clear", args=[self.goal_a.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(response, f"{reverse('core:login')}?next={url}")

        self.assertEqual(AIFeedback.objects.count(), 1)

    def test_fremder_eintrag_404_ohne_loeschung(self):
        fremd = self.eintrag(self.goal_b)
        response = self.client.post(reverse("core:ai_feedback_delete", args=[fremd.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(AIFeedback.objects.filter(pk=fremd.pk).exists())

    def test_fremdes_goal_zuruecksetzen_404(self):
        self.eintrag(self.goal_b)
        url = reverse("core:goal_ai_history_clear", args=[self.goal_b.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(AIFeedback.objects.filter(goal=self.goal_b).count(), 1)

    def test_eigene_loeschung_funktioniert(self):
        # Gegenprobe: ohne sie waeren die 404-Tests trivial erfuellbar.
        eigen = self.eintrag(self.goal_a)
        response = self.client.post(reverse("core:ai_feedback_delete", args=[eigen.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AIFeedback.objects.exists())
