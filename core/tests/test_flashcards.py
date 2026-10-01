"""KI-Lernkarten: Modell, Service (Structured Output, Parser), Views, Anzeige, Isolation."""

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import Flashcard, Goal, LearningSession, Resource
from core.services import ai_service
from core.services.ai_service import AIServiceError

User = get_user_model()

PASSWORT = "ein-sicheres-Passwort-2026"
# Platzhalter nach der Projektkonvention -- kein schluesselartiges Literal.
TEST_SCHLUESSEL = "test-schluessel-platzhalter"
LOGGER = "core.services.ai_service"


def karten_json(*paare):
    return json.dumps({"cards": [{"question": f, "answer": a} for f, a in paare]})


DREI_KARTEN = karten_json(
    ("Was macht annotate()?", "Haengt pro Zeile einen berechneten Wert an."),
    ("Was macht aggregate()?", "Berechnet einen Wert ueber das ganze Queryset."),
    ("Wozu dient F()?", "Verweist in einer Abfrage auf ein Feld."),
)


def sdk_antwort(content, refusal=None):
    """Patcht das SDK mit einer festen Antwort; nie ein echter Aufruf."""
    nachricht = SimpleNamespace(content=content, refusal=refusal)
    antwort = SimpleNamespace(choices=[SimpleNamespace(message=nachricht)])
    return patch(
        "core.services.ai_service.OpenAI",
        **{"return_value.chat.completions.create.return_value": antwort},
    )


class FlashcardTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user(username="nutzer_a", password=PASSWORT)
        cls.user_b = User.objects.create_user(username="nutzer_b", password=PASSWORT)
        cls.goal_a = Goal.objects.create(user=cls.user_a, title="Django ORM")
        cls.goal_a2 = Goal.objects.create(user=cls.user_a, title="Zweites Ziel von A")
        cls.goal_b = Goal.objects.create(user=cls.user_b, title="Geheimes Ziel von B")

        LearningSession.objects.create(
            goal=cls.goal_a,
            date=datetime.date(2026, 9, 15),
            duration=45,
            notes="annotate vs aggregate geuebt",
        )
        Resource.objects.create(
            goal=cls.goal_a, url="https://example.com/orm", title="ORM-Doku", type="doc"
        )
        LearningSession.objects.create(
            goal=cls.goal_b,
            date=datetime.date(2026, 9, 15),
            duration=30,
            notes="Notiz von B, streng privat",
        )

    def karte(self, goal, frage="Frage?", antwort="Antwort.", gelernt=False, minuten_alt=None):
        karte = Flashcard.objects.create(
            goal=goal, question=frage, answer=antwort, is_mastered=gelernt
        )
        if minuten_alt is not None:
            Flashcard.objects.filter(pk=karte.pk).update(
                created_at=timezone.now() - datetime.timedelta(minutes=minuten_alt)
            )
            karte.refresh_from_db()
        return karte


# --- Modell -----------------------------------------------------------------


class ModellTests(FlashcardTestCase):
    def test_offene_vor_gelernten_darin_neueste_zuerst(self):
        alt_offen = self.karte(self.goal_a, "alt offen", minuten_alt=60)
        neu_offen = self.karte(self.goal_a, "neu offen", minuten_alt=1)
        gelernt = self.karte(self.goal_a, "gelernt", gelernt=True, minuten_alt=0)

        self.assertEqual(list(self.goal_a.flashcards.all()), [neu_offen, alt_offen, gelernt])

    def test_cascade_beim_goal_loeschen(self):
        self.karte(self.goal_a)
        self.goal_a.delete()
        self.assertFalse(Flashcard.objects.exists())


# --- Service: Mock ----------------------------------------------------------


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class MockTests(FlashcardTestCase):
    def test_drei_deterministische_karten_ohne_api(self):
        with patch("core.services.ai_service._call_openai") as aufruf:
            erste = ai_service.generate_flashcards(self.goal_a)
            zweite = ai_service.generate_flashcards(self.goal_a)

        aufruf.assert_not_called()
        self.assertEqual(erste, zweite)
        self.assertEqual(len(erste), 3)
        self.assertIn("Django ORM", erste[0]["question"])
        for karte in erste:
            self.assertEqual(set(karte), {"question", "answer"})

    def test_mock_erzeugt_keine_duplikate(self):
        for karte in ai_service.generate_flashcards(self.goal_a)[1:]:
            self.karte(self.goal_a, karte["question"])

        # Nur die noch fehlende Beispielkarte wird erneut geliefert.
        neu = ai_service.generate_flashcards(self.goal_a)
        self.assertEqual(len(neu), 1)
        self.assertIn("Django ORM", neu[0]["question"])

        self.karte(self.goal_a, neu[0]["question"])
        with self.assertRaises(AIServiceError) as ctx:
            ai_service.generate_flashcards(self.goal_a)
        self.assertIn("Mock-Modus", str(ctx.exception))


# --- Service: SDK-Aufruf ----------------------------------------------------


@override_settings(AI_MOCK_MODE=False, OPENAI_API_KEY=TEST_SCHLUESSEL, OPENAI_MODEL="gpt-4o-mini")
class SdkAufrufTests(FlashcardTestCase):
    def aufruf_kwargs(self):
        with sdk_antwort(DREI_KARTEN) as sdk:
            ai_service.generate_flashcards(self.goal_a)
        return sdk.return_value.chat.completions.create.call_args.kwargs

    def test_structured_output_mit_strict_schema(self):
        format_ = self.aufruf_kwargs()["response_format"]

        self.assertEqual(format_["type"], "json_schema")
        self.assertTrue(format_["json_schema"]["strict"])
        schema = format_["json_schema"]["schema"]
        karte = schema["properties"]["cards"]["items"]
        # Strict-Modus: alle Felder required, keine Zusatzfelder -- auf jeder Ebene.
        self.assertEqual(schema["required"], ["cards"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(sorted(karte["required"]), ["answer", "question"])
        self.assertFalse(karte["additionalProperties"])

    def test_konfiguriertes_modell(self):
        self.assertEqual(self.aufruf_kwargs()["model"], "gpt-4o-mini")

    def test_textaktionen_ohne_response_format(self):
        """Zusammenfassung und Schritte bleiben unveraendert reine Textaufrufe."""
        with sdk_antwort("Ein Text.") as sdk:
            ai_service.generate_summary(self.goal_a)
        self.assertNotIn(
            "response_format", sdk.return_value.chat.completions.create.call_args.kwargs
        )

    def test_prompt_nur_mit_eigenen_goal_daten(self):
        prompt = self.aufruf_kwargs()["messages"][0]["content"]

        self.assertIn("Django ORM", prompt)
        self.assertIn("annotate vs aggregate geuebt", prompt)
        self.assertIn("ORM-Doku", prompt)
        self.assertNotIn("Geheimes Ziel von B", prompt)
        self.assertNotIn("Notiz von B", prompt)

    def test_vorhandene_fragen_im_prompt(self):
        self.karte(self.goal_a, "Was ist ein QuerySet?")
        self.karte(self.goal_a2, "Frage aus einem anderen Goal")

        prompt = self.aufruf_kwargs()["messages"][0]["content"]

        self.assertIn("Was ist ein QuerySet?", prompt)
        self.assertNotIn("Frage aus einem anderen Goal", prompt)

    def test_gueltige_antwort_wird_geliefert(self):
        with sdk_antwort(DREI_KARTEN):
            karten = ai_service.generate_flashcards(self.goal_a)
        self.assertEqual(len(karten), 3)
        self.assertEqual(karten[0]["question"], "Was macht annotate()?")

    def test_refusal_wird_eigener_fehler(self):
        with sdk_antwort(None, refusal="Ich kann dabei nicht helfen."):
            with self.assertLogs(LOGGER, level="WARNING"):
                with self.assertRaises(AIServiceError) as ctx:
                    ai_service.generate_flashcards(self.goal_a)
        # Nicht in die generische "nicht verfuegbar"-Meldung umgedeutet.
        self.assertIn("abgelehnt", str(ctx.exception))


# --- Service: Parser --------------------------------------------------------


class ParserTests(TestCase):
    def assertParserFehler(self, rohtext):
        with self.assertLogs(LOGGER, level="WARNING"):
            with self.assertRaises(AIServiceError) as ctx:
                ai_service._parse_flashcards(rohtext)
        self.assertNotIn("Traceback", str(ctx.exception))

    def test_ungueltiges_json(self):
        self.assertParserFehler('{"cards": [{"question": "abgeschnitten')

    def test_liste_statt_objekt(self):
        self.assertParserFehler('[{"question": "a", "answer": "b"}]')

    def test_cards_fehlt_oder_kein_array(self):
        self.assertParserFehler('{"karten": []}')
        self.assertParserFehler('{"cards": "keine Liste"}')

    def test_leere_und_unvollstaendige_eintraege_verworfen(self):
        rohtext = json.dumps({"cards": [
            {"question": "  Gueltig 1  ", "answer": " A1 "},
            {"question": "", "answer": "ohne Frage"},
            {"question": "ohne Antwort", "answer": "   "},
            {"question": "nur Frage"},
            "kein Objekt",
            {"question": 42, "answer": "keine Zeichenkette"},
            {"question": "Gueltig 2", "answer": "A2"},
            {"question": "Gueltig 3", "answer": "A3"},
        ]})

        karten = ai_service._parse_flashcards(rohtext)

        self.assertEqual(
            karten,
            [
                {"question": "Gueltig 1", "answer": "A1"},
                {"question": "Gueltig 2", "answer": "A2"},
                {"question": "Gueltig 3", "answer": "A3"},
            ],
        )

    def test_zu_wenige_karten(self):
        self.assertParserFehler(karten_json(("F1", "A1"), ("F2", "A2")))

    def test_zu_viele_karten_werden_gekuerzt(self):
        rohtext = karten_json(*[(f"F{i}", f"A{i}") for i in range(1, 8)])
        karten = ai_service._parse_flashcards(rohtext)
        self.assertEqual([k["question"] for k in karten], ["F1", "F2", "F3", "F4", "F5"])

    def test_duplikate_in_antwort_und_gegen_bestand(self):
        rohtext = karten_json(
            ("Was ist F()?", "A"),
            ("  was ist f()?  ", "Duplikat innerhalb der Antwort"),
            ("Was ist Q()?", "Duplikat gegen den Bestand"),
            ("Neu 1", "A"),
            ("Neu 2", "A"),
        )

        karten = ai_service._parse_flashcards(rohtext, vorhandene_fragen=["WAS IST Q()?"])

        self.assertEqual([k["question"] for k in karten], ["Was ist F()?", "Neu 1", "Neu 2"])

    def test_nur_duplikate_ergeben_fehler(self):
        rohtext = karten_json(("A?", "1"), ("B?", "2"), ("C?", "3"))
        with self.assertLogs(LOGGER, level="WARNING"):
            with self.assertRaises(AIServiceError):
                ai_service._parse_flashcards(rohtext, vorhandene_fragen=["a?", "b?"])


# --- Views ------------------------------------------------------------------


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class GenerierenViewTests(FlashcardTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)
        self.url = reverse("core:goal_ai_flashcards", args=[self.goal_a.pk])

    def test_karten_werden_angehaengt_lernstatus_bleibt(self):
        vorhanden = self.karte(self.goal_a, "Vorhandene Frage", gelernt=True)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("core:goal_detail", args=[self.goal_a.pk]) + "#lernkarten",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.goal_a.flashcards.count(), 4)
        vorhanden.refresh_from_db()
        self.assertTrue(vorhanden.is_mastered)

    def test_reihenfolge_der_ki_bleibt_neue_durchlaeufe_oben(self):
        def durchlauf(*fragen):
            karten = [{"question": f, "answer": "A"} for f in fragen]
            with patch("core.services.ai_service.generate_flashcards", return_value=karten):
                self.client.post(self.url)

        durchlauf("Alt 1", "Alt 2", "Alt 3")
        durchlauf("Neu 1", "Neu 2", "Neu 3")

        self.assertEqual(
            list(self.goal_a.flashcards.values_list("question", flat=True)),
            ["Neu 1", "Neu 2", "Neu 3", "Alt 1", "Alt 2", "Alt 3"],
        )

    def test_meldung_im_abschnitt_genau_einmal(self):
        html = self.client.post(self.url, follow=True).content.decode()
        self.assertEqual(html.count("3 Lernkarten erstellt."), 1)
        self.assertGreater(html.index("3 Lernkarten erstellt."), html.index('id="lernkarten"'))

    def test_meldung_in_der_einzahl(self):
        with patch(
            "core.services.ai_service.generate_flashcards",
            return_value=[{"question": "Einzige Frage", "answer": "A"}],
        ):
            response = self.client.post(self.url, follow=True)
        self.assertContains(response, "1 Lernkarte erstellt.")

    def test_fehler_speichert_nichts_meldung_im_abschnitt(self):
        with patch(
            "core.services.ai_service.generate_flashcards",
            side_effect=AIServiceError("Die KI hat keine verwertbaren Lernkarten geliefert."),
        ):
            html = self.client.post(self.url, follow=True).content.decode()

        self.assertFalse(Flashcard.objects.exists())
        self.assertEqual(html.count("keine verwertbaren Lernkarten"), 1)
        self.assertGreater(
            html.index("keine verwertbaren Lernkarten"), html.index('id="lernkarten"')
        )
        self.assertIn('class="alert alert-danger', html)

    def test_nicht_per_get(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(Flashcard.objects.exists())


class VerwaltenViewTests(FlashcardTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def test_umschalten_hin_und_zurueck(self):
        karte = self.karte(self.goal_a)
        url = reverse("core:flashcard_toggle", args=[karte.pk])

        response = self.client.post(url)
        karte.refresh_from_db()
        self.assertTrue(karte.is_mastered)
        self.assertRedirects(
            response,
            reverse("core:goal_detail", args=[self.goal_a.pk]) + "#lernkarten",
            fetch_redirect_response=False,
        )

        self.client.post(url)
        karte.refresh_from_db()
        self.assertFalse(karte.is_mastered)

    def test_loeschen_nur_dieser_karte(self):
        weg = self.karte(self.goal_a, "weg")
        bleibt = self.karte(self.goal_a, "bleibt")

        self.client.post(reverse("core:flashcard_delete", args=[weg.pk]))

        self.assertEqual(list(Flashcard.objects.all()), [bleibt])

    def test_nicht_per_get(self):
        karte = self.karte(self.goal_a)
        for name in ("core:flashcard_toggle", "core:flashcard_delete"):
            with self.subTest(route=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=[karte.pk])).status_code, 405
                )
        karte.refresh_from_db()
        self.assertFalse(karte.is_mastered)


# --- Anzeige ----------------------------------------------------------------


class AnzeigeTests(FlashcardTestCase):
    def setUp(self):
        self.client.force_login(self.user_a)

    def detail(self, goal=None):
        response = self.client.get(reverse("core:goal_detail", args=[(goal or self.goal_a).pk]))
        self.assertEqual(response.status_code, 200)
        return response

    def test_frage_im_kopf_antwort_eingeklappt(self):
        karte = self.karte(self.goal_a, "Was ist select_related?", "Ein JOIN fuer FKs.")
        html = self.detail().content.decode()

        kopf = html[html.index(f'id="karte-{karte.pk}-kopf"') :]
        kopf = kopf[: kopf.index("</h3>")]
        self.assertIn('class="accordion-button collapsed', kopf)
        self.assertIn('aria-expanded="false"', kopf)
        self.assertIn("Was ist select_related?", kopf)
        self.assertNotIn("Ein JOIN fuer FKs.", kopf)

        body = html[html.index(f'id="karte-{karte.pk}" class="accordion-collapse collapse"') :]
        self.assertIn("Ein JOIN fuer FKs.", body[: body.index('</div>\n                </div>')])

    def test_gelernt_badge_und_fortschritt(self):
        self.karte(self.goal_a, "offen")
        self.karte(self.goal_a, "gelernt", gelernt=True)

        response = self.detail()

        self.assertContains(response, "</i>Gelernt</span>", count=1)
        self.assertContains(response, "1 von 2 gelernt")
        self.assertContains(response, 'aria-valuenow="50"')

    def test_offene_karten_zuerst(self):
        self.karte(self.goal_a, "Gelernte Frage", gelernt=True, minuten_alt=0)
        self.karte(self.goal_a, "Offene Frage", minuten_alt=30)
        html = self.detail().content.decode()
        self.assertLess(html.index("Offene Frage"), html.index("Gelernte Frage"))

    def test_leerzustand(self):
        response = self.detail()
        self.assertContains(response, "Noch keine Lernkarten.")
        self.assertNotContains(response, "von 0 gelernt")

    def test_abfragen_unabhaengig_von_kartenzahl(self):
        def anzahl_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.detail()
            return len(ctx.captured_queries)

        for i in range(2):
            self.karte(self.goal_a, f"F{i}")
        bei_zwei = anzahl_queries()
        for i in range(6):
            self.karte(self.goal_a, f"G{i}", gelernt=bool(i % 2))
        bei_acht = anzahl_queries()

        self.assertEqual(bei_zwei, bei_acht)

    def test_karten_anderer_goals_unsichtbar(self):
        self.karte(self.goal_a, "Nur fuer Goal A")
        self.assertNotContains(self.detail(self.goal_a2), "Nur fuer Goal A")

    def test_ki_text_wird_escaped(self):
        self.karte(self.goal_a, "<script>alert(1)</script>", "<b>fett</b>")
        response = self.detail()
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<b>fett</b>")


# --- Isolation --------------------------------------------------------------


@override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
class ScopingTests(FlashcardTestCase):
    def test_login_pflicht(self):
        karte = self.karte(self.goal_a)
        for url in (
            reverse("core:goal_ai_flashcards", args=[self.goal_a.pk]),
            reverse("core:flashcard_toggle", args=[karte.pk]),
            reverse("core:flashcard_delete", args=[karte.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(response, f"{reverse('core:login')}?next={url}")
        self.assertEqual(Flashcard.objects.count(), 1)
        karte.refresh_from_db()
        self.assertFalse(karte.is_mastered)

    def test_fremdes_goal_404_ohne_service_aufruf(self):
        self.client.force_login(self.user_a)
        with patch("core.services.ai_service.generate_flashcards") as service:
            response = self.client.post(
                reverse("core:goal_ai_flashcards", args=[self.goal_b.pk])
            )
        self.assertEqual(response.status_code, 404)
        service.assert_not_called()
        self.assertFalse(Flashcard.objects.exists())

    def test_fremde_karte_umschalten_und_loeschen_404(self):
        fremd = self.karte(self.goal_b, "Karte von B")
        self.client.force_login(self.user_a)

        for name in ("core:flashcard_toggle", "core:flashcard_delete"):
            with self.subTest(route=name):
                response = self.client.post(reverse(name, args=[fremd.pk]))
                self.assertEqual(response.status_code, 404)

        fremd.refresh_from_db()
        self.assertFalse(fremd.is_mastered)

    def test_gegenprobe_eigene_karte(self):
        # Ohne sie waeren die 404-Tests trivial erfuellbar.
        eigen = self.karte(self.goal_a)
        self.client.force_login(self.user_a)
        self.assertEqual(
            self.client.post(reverse("core:flashcard_toggle", args=[eigen.pk])).status_code, 302
        )
        self.assertEqual(
            self.client.post(reverse("core:flashcard_delete", args=[eigen.pk])).status_code, 302
        )
        self.assertFalse(Flashcard.objects.exists())
