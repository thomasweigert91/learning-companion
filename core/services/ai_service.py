"""Anbindung der OpenAI-API fuer Fortschritts-Zusammenfassungen und Lernschritte.

Dies ist die einzige Stelle im Projekt, die das openai-SDK kennt. Views und
Templates rufen ausschliesslich die beiden oeffentlichen Funktionen auf und
sehen nur AIServiceError -- nie einen SDK-Fehlertyp.
"""

import json
import logging

from django.conf import settings
from openai import APITimeoutError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


# Obergrenzen fuer den Prompt-Kontext. Ohne sie waechst der Prompt mit dem
# Datenbestand und sprengt irgendwann Kontextfenster und Kostenbudget.
MAX_SESSIONS = 10
MAX_RESOURCES = 20

# Wie viele Lernschritte die Antwort hoechstens enthalten darf. Die Zusage
# wird im Code durchgesetzt, nicht dem Modell ueberlassen.
MIN_STEPS = 2
MAX_STEPS = 3

# Ein Rate-Limit soll nicht zu langen Wartezeiten im Request fuehren.
MAX_RETRIES = 1

# Lernkarten: Anzahl pro Aufruf, im Code durchgesetzt. Vorhandene Fragen gehen
# gedeckelt in den Prompt, damit die KI keine Duplikate erzeugt.
MIN_FLASHCARDS = 3
MAX_FLASHCARDS = 5
MAX_EXISTING_QUESTIONS = 30

# Structured Output im Strict-Modus: required fuer alle Felder und
# additionalProperties: false auf jeder Objektebene. minItems/maxItems stehen
# bewusst nicht im Schema -- die Anzahl setzt _parse_flashcards durch, und ein
# im Strict-Modus nicht unterstuetztes Schluesselwort liesse jede Anfrage mit
# einem Schemafehler scheitern.
FLASHCARD_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "lernkarten",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                        "required": ["question", "answer"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["cards"],
            "additionalProperties": False,
        },
    },
}


class AIServiceError(Exception):
    """Die einzige Exception, die diesen Service verlaesst."""


def max_request_seconds():
    """Obergrenze, wie lange ein KI-Request im schlimmsten Fall dauern kann.

    Jeder Versuch darf das Timeout ausschoepfen, dazu kommt die Wartezeit des
    SDK zwischen den Versuchen (grosszuegig mit 10 s pro Wiederholung). Die
    Detailseite gibt gesperrte KI-Buttons erst nach dieser Frist wieder frei --
    vorher liefe der erste Request womoeglich noch.
    """
    return settings.OPENAI_TIMEOUT_SECONDS * (MAX_RETRIES + 1) + 10 * MAX_RETRIES


def is_mock_mode():
    """Mock ist aktiv, wenn er eingeschaltet ist ODER kein Schluessel vorliegt.

    Damit bleibt die Anwendung lokal ohne API-Key benutzbar, statt beim ersten
    Klick zu scheitern.
    """
    return bool(settings.AI_MOCK_MODE) or not settings.OPENAI_API_KEY


# --- Prompt-Bau -------------------------------------------------------------
# Jede Query geht vom uebergebenen Goal aus. Dadurch koennen strukturell keine
# Daten anderer Nutzer in den Prompt geraten.


def _format_context(goal):
    sessions = list(goal.sessions.all()[:MAX_SESSIONS])
    resources = list(goal.resources.all()[:MAX_RESOURCES])

    zeilen = [
        f"Lernziel: {goal.title}",
        f"Status: {goal.get_status_display()}",
    ]
    if goal.description:
        zeilen.append(f"Beschreibung: {goal.description}")

    if sessions:
        zeilen.append("")
        zeilen.append("Bisherige Lernsitzungen:")
        for session in sessions:
            notiz = session.notes.strip() or "(keine Notizen)"
            zeilen.append(
                f"- {session.date:%d.%m.%Y}, {session.duration} Minuten: {notiz}"
            )
    else:
        zeilen.append("")
        zeilen.append("Bisher wurden keine Lernsitzungen erfasst.")

    if resources:
        zeilen.append("")
        zeilen.append("Hinterlegte Ressourcen:")
        for resource in resources:
            zeilen.append(f"- [{resource.get_type_display()}] {resource.title}")

    return "\n".join(zeilen)


def _build_summary_prompt(goal):
    return (
        "Fasse den Lernfortschritt zu folgendem Lernziel zusammen. "
        "Gehe auf den bisherigen Aufwand, erkennbare Schwerpunkte und den "
        "aktuellen Stand ein. Antworte auf Deutsch in hoechstens drei "
        "kurzen Absaetzen.\n\n"
        f"{_format_context(goal)}"
    )


def _build_next_steps_prompt(goal):
    return (
        f"Schlage {MIN_STEPS} bis {MAX_STEPS} konkrete naechste Lernschritte "
        "fuer folgendes Lernziel vor. Antworte auf Deutsch. Gib ausschliesslich "
        "die Schritte aus, einen pro Zeile, ohne Nummerierung und ohne "
        "einleitenden Satz.\n\n"
        f"{_format_context(goal)}"
    )


def _build_flashcards_prompt(goal, vorhandene_fragen):
    prompt = (
        f"Erstelle {MIN_FLASHCARDS} bis {MAX_FLASHCARDS} Lernkarten zu folgendem "
        "Lernziel. Jede Karte besteht aus einer Frage und einer knappen Antwort. "
        "Die Fragen sollen pruefen, ob die Inhalte aus den Notizen und "
        "Ressourcen verstanden wurden, und muessen sich aus diesem Kontext "
        "beantworten lassen. Antworte auf Deutsch.\n\n"
        f"{_format_context(goal)}"
    )
    if vorhandene_fragen:
        prompt += "\n\nDiese Fragen existieren bereits, erzeuge sie nicht erneut:\n"
        prompt += "\n".join(f"- {frage}" for frage in vorhandene_fragen)
    return prompt


def _frage_schluessel(frage):
    """Vergleichsschluessel fuer Duplikate: ohne Raender, ohne Gross-/Kleinschreibung."""
    return frage.strip().casefold()


def _ohne_duplikate(karten, vorhandene_fragen):
    """Verwirft Karten, deren Frage schon vorkommt -- in der Liste oder im Bestand."""
    gesehen = {_frage_schluessel(frage) for frage in vorhandene_fragen}
    eindeutig = []
    for karte in karten:
        schluessel = _frage_schluessel(karte["question"])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        eindeutig.append(karte)
    return eindeutig


def _parse_flashcards(rohtext, vorhandene_fragen=()):
    """Validiert die JSON-Antwort und liefert 3 bis 5 bereinigte Karten.

    Jeder Fehlerfall wird protokolliert und endet in AIServiceError -- nie in
    einer halben Kartenliste oder einem 500er.
    """
    unverwertbar = (
        "Die KI hat keine verwertbaren Lernkarten geliefert. "
        "Bitte versuche es erneut."
    )

    try:
        daten = json.loads(rohtext)
    except json.JSONDecodeError:
        logger.warning("Lernkarten-Antwort ist kein gueltiges JSON")
        raise AIServiceError(unverwertbar) from None

    karten_roh = daten.get("cards") if isinstance(daten, dict) else None
    if not isinstance(karten_roh, list):
        logger.warning("Lernkarten-Antwort hat nicht die erwartete Struktur")
        raise AIServiceError(unverwertbar)

    karten = []
    for eintrag in karten_roh:
        if not isinstance(eintrag, dict):
            continue
        frage, antwort = eintrag.get("question"), eintrag.get("answer")
        if not (isinstance(frage, str) and isinstance(antwort, str)):
            continue
        frage, antwort = frage.strip(), antwort.strip()
        if frage and antwort:
            karten.append({"question": frage, "answer": antwort})
    karten = _ohne_duplikate(karten, vorhandene_fragen)

    if len(karten) < MIN_FLASHCARDS:
        logger.warning(
            "Nur %s verwertbare Lernkarten in der Antwort (mindestens %s)",
            len(karten),
            MIN_FLASHCARDS,
        )
        raise AIServiceError(unverwertbar)

    return karten[:MAX_FLASHCARDS]


# --- SDK-Kontakt ------------------------------------------------------------


def _call_openai(prompt, response_format=None):
    """Einziger Kontaktpunkt zum SDK. Uebersetzt alle Fehler in AIServiceError.

    response_format wird nur durchgereicht, wenn gesetzt -- die Text-Aufrufe
    bleiben damit unveraendert.
    """
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )

    optionen = {"response_format": response_format} if response_format else {}

    try:
        antwort = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            **optionen,
        )
        nachricht = antwort.choices[0].message
        # Bei Structured Outputs kann das Modell ablehnen, statt das Schema zu
        # fuellen. Nur ein echter String zaehlt -- so bleiben Antworten ohne
        # das Feld (und Test-Doubles) unberuehrt.
        refusal = getattr(nachricht, "refusal", None)
        if isinstance(refusal, str) and refusal.strip():
            logger.warning("OpenAI hat die Anfrage abgelehnt")
            raise AIServiceError(
                "Die KI hat die Anfrage abgelehnt. "
                "Bitte pruefe die Notizen und versuche es erneut."
            )
        return nachricht.content or ""
    except AIServiceError:
        # Eigene Fehler unveraendert weiterreichen -- sonst wuerden sie unten
        # in "nicht verfuegbar" umgedeutet.
        raise
    except APITimeoutError:
        logger.warning("OpenAI-Timeout nach %ss", settings.OPENAI_TIMEOUT_SECONDS)
        # from None: der Originalfehler steht im Log, die Kette wird bewusst
        # gekappt, damit kein SDK-Trace in die Oberflaeche durchschlaegt.
        raise AIServiceError(
            "Die KI-Antwort hat zu lange gedauert. Bitte versuche es erneut."
        ) from None
    except RateLimitError:
        logger.warning("OpenAI-Rate-Limit erreicht")
        raise AIServiceError(
            "Das Anfragelimit der KI ist erreicht. Bitte versuche es spaeter erneut."
        ) from None
    except Exception:
        # Der Originalfehler geht ins Log, nicht in die Oberflaeche: so landen
        # weder Stacktrace noch SDK-Rohtext noch ein Key-Fragment beim Nutzer.
        logger.exception("Unerwarteter Fehler beim OpenAI-Aufruf")
        raise AIServiceError(
            "Die KI-Funktion ist momentan nicht verfuegbar. "
            "Bitte versuche es spaeter erneut."
        ) from None


# --- Mock -------------------------------------------------------------------
# Deterministisch und aus den echten Goal-Daten abgeleitet, damit die
# Oberflaeche im Mock-Betrieb plausibel aussieht statt nur Platzhalter zu zeigen.


def _mock_summary(goal):
    sessions = list(goal.sessions.all()[:MAX_SESSIONS])
    gesamt = sum(session.duration for session in sessions)
    anzahl_ressourcen = goal.resources.count()

    return (
        f"[Mock-Modus] Zum Lernziel „{goal.title}“ sind "
        f"{len(sessions)} Lernsitzungen mit insgesamt {gesamt} Minuten erfasst. "
        f"Hinterlegt sind {anzahl_ressourcen} Ressourcen. "
        f"Der Status ist aktuell: {goal.get_status_display()}."
    )


def _mock_flashcards(goal):
    sessions = list(goal.sessions.all()[:MAX_SESSIONS])
    gesamt = sum(session.duration for session in sessions)
    anzahl_ressourcen = goal.resources.count()

    return [
        {
            "question": f"[Mock-Modus] Worum geht es im Lernziel „{goal.title}“?",
            "answer": f"Um „{goal.title}“, aktueller Status: {goal.get_status_display()}.",
        },
        {
            "question": "[Mock-Modus] Wie viel Lernzeit ist bisher erfasst?",
            "answer": f"{len(sessions)} Lernsitzungen mit insgesamt {gesamt} Minuten.",
        },
        {
            "question": "[Mock-Modus] Wie viele Ressourcen sind hinterlegt?",
            "answer": f"{anzahl_ressourcen} Ressourcen.",
        },
    ]


def _mock_next_steps(goal):
    return [
        f"[Mock-Modus] Eine weitere Lernsitzung zu „{goal.title}“ einplanen.",
        "[Mock-Modus] Die hinterlegten Ressourcen durcharbeiten und Notizen ergaenzen.",
        "[Mock-Modus] Den Status des Lernziels ueberpruefen und aktualisieren.",
    ]


# --- Oeffentliche Schnittstelle ---------------------------------------------


def generate_summary(goal):
    """Liefert eine Fortschrittszusammenfassung als Text. Schreibt nichts in die DB."""
    if is_mock_mode():
        return _mock_summary(goal)
    return _call_openai(_build_summary_prompt(goal)).strip()


def suggest_next_steps(goal):
    """Liefert 2 bis 3 naechste Lernschritte als Liste. Schreibt nichts in die DB."""
    if is_mock_mode():
        return _mock_next_steps(goal)[:MAX_STEPS]

    rohtext = _call_openai(_build_next_steps_prompt(goal))

    schritte = []
    for zeile in rohtext.splitlines():
        # Haeufige Listenpraefixe entfernen, falls das Modell sie doch setzt.
        bereinigt = zeile.strip().lstrip("-*• ").strip()
        if bereinigt and bereinigt[0].isdigit():
            bereinigt = bereinigt.lstrip("0123456789.) ").strip()
        if bereinigt:
            schritte.append(bereinigt)

    if not schritte:
        raise AIServiceError(
            "Die KI hat keine verwertbaren Lernschritte geliefert. "
            "Bitte versuche es erneut."
        )

    return schritte[:MAX_STEPS]


def generate_flashcards(goal):
    """Liefert 3 bis 5 Lernkarten als Liste von Dicts. Schreibt nichts in die DB.

    Bereits vorhandene Fragen des Goals werden der KI mitgegeben und beim
    Parsen als Duplikate verworfen.
    """
    vorhandene_fragen = list(
        goal.flashcards.values_list("question", flat=True)[:MAX_EXISTING_QUESTIONS]
    )

    if is_mock_mode():
        # Auch der Mock erzeugt keine Duplikate -- sonst legte jeder Klick
        # dieselben Beispielkarten erneut an.
        karten = _ohne_duplikate(_mock_flashcards(goal), vorhandene_fragen)
        if not karten:
            raise AIServiceError(
                "[Mock-Modus] Alle Beispiel-Lernkarten sind bereits vorhanden. "
                "Fuer neue Karten wird ein OpenAI-Schluessel benoetigt."
            )
        return karten

    rohtext = _call_openai(
        _build_flashcards_prompt(goal, vorhandene_fragen),
        response_format=FLASHCARD_RESPONSE_FORMAT,
    )
    return _parse_flashcards(rohtext, vorhandene_fragen)
