"""Anbindung der OpenAI-API fuer Fortschritts-Zusammenfassungen und Lernschritte.

Dies ist die einzige Stelle im Projekt, die das openai-SDK kennt. Views und
Templates rufen ausschliesslich die beiden oeffentlichen Funktionen auf und
sehen nur AIServiceError -- nie einen SDK-Fehlertyp.
"""

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


class AIServiceError(Exception):
    """Die einzige Exception, die diesen Service verlaesst."""


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


# --- SDK-Kontakt ------------------------------------------------------------


def _call_openai(prompt):
    """Einziger Kontaktpunkt zum SDK. Uebersetzt alle Fehler in AIServiceError."""
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        # Ein Rate-Limit soll nicht zu langen Wartezeiten im Request fuehren.
        max_retries=1,
    )

    try:
        antwort = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return antwort.choices[0].message.content or ""
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
