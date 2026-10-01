"""Export der eigenen Daten: Sitzungen als CSV, Goals als Markdown-ZIP, JSON-Dump.

Das Modul liest nur. Jeder Einstieg nimmt den Nutzer entgegen und filtert selbst
auf ihn -- Goals ueber user, Sitzungen ueber goal__user, alle weiteren Kind-Daten
per Prefetch ueber die bereits gescopten Goals. Ein Aufrufer kann damit gar keine
fremden Daten anfordern.
"""

import csv
import io
import json
import zipfile
from collections import Counter

from django.db.models import Prefetch
from django.utils import timezone
from django.utils.text import slugify

from core.models import Goal, LearningSession, Profile

CSV_HEADER = ["Goal", "Date", "Duration (min)", "Tags", "Notes"]
# Zeichen, mit denen Tabellenkalkulationen eine Zelle als Formel auswerten
# (OWASP "CSV Injection"). Solche Zellen bekommen ein fuehrendes Apostroph.
CSV_FORMEL_PRAEFIXE = ("=", "+", "-", "@", "\t", "\r")
CSV_CHUNK_SIZE = 500
# Ohne BOM zeigt Excel UTF-8-Umlaute als Zeichensalat an.
UTF8_BOM = "﻿"
TAG_TRENNER = "; "

MAX_SLUG_LAENGE = 50
# Erhoehen, sobald sich die Struktur des JSON-Dumps inkompatibel aendert.
FORMAT_VERSION = 1


def export_filename(art, endung):
    """z. B. learning-companion-sessions-2026-10-01.csv"""
    return f"learning-companion-{art}-{timezone.localdate():%Y-%m-%d}.{endung}"


# --- CSV ----------------------------------------------------------------------


class _Zeilenpuffer:
    """Pseudo-Datei fuer csv.writer: writerow() liefert die Zeile direkt zurueck.

    So entsteht jede CSV-Zeile einzeln und kann gestreamt werden, ohne dass die
    ganze Datei im Speicher liegt.
    """

    def write(self, zeile):
        return zeile


def _csv_safe(wert):
    if wert.startswith(CSV_FORMEL_PRAEFIXE):
        return f"'{wert}"
    return wert


def sessions_for_export(user):
    # Tags kommen ueber Tag.Meta.ordering bereits alphabetisch.
    return (
        LearningSession.objects.filter(goal__user=user)
        .select_related("goal")
        .prefetch_related("tags")
        .order_by("date", "pk")
    )


def session_csv_row(session):
    return [
        _csv_safe(session.goal.title),
        session.date.isoformat(),
        session.duration,
        _csv_safe(TAG_TRENNER.join(tag.name for tag in session.tags.all())),
        _csv_safe(session.notes),
    ]


def iter_sessions_csv(user):
    """Liefert die CSV zeilenweise; die erste Ausgabe ist BOM plus Header.

    iterator(chunk_size=...) laedt die Sitzungen blockweise. Seit Django 4.1
    greift prefetch_related auch dabei -- je Block eine Tag-Abfrage, kein N+1.
    """
    writer = csv.writer(_Zeilenpuffer())
    yield UTF8_BOM + writer.writerow(CSV_HEADER)
    for session in sessions_for_export(user).iterator(chunk_size=CSV_CHUNK_SIZE):
        yield writer.writerow(session_csv_row(session))


# --- Markdown-ZIP -------------------------------------------------------------


def goals_for_export(user):
    """Eigene Goals mit Sitzungen (chronologisch, mit Tags) und Ressourcen."""
    return (
        Goal.objects.filter(user=user)
        .order_by("pk")
        .prefetch_related(
            Prefetch(
                "sessions",
                queryset=LearningSession.objects.order_by("date", "pk").prefetch_related("tags"),
            ),
            "resources",
        )
    )


def goal_filename(goal):
    """goals/<pk>-<slug>.md -- der PK macht den Namen auch bei gleichem Titel eindeutig."""
    slug = slugify(goal.title)[:MAX_SLUG_LAENGE].strip("-") or "goal"
    return f"goals/{goal.pk}-{slug}.md"


def _yaml_str(wert):
    """Ein JSON-String ist zugleich ein gueltiger YAML-Double-Quoted-Scalar.

    Damit koennen ":", '"', "#" oder Zeilenumbrueche im Titel die Frontmatter
    nicht aufbrechen.
    """
    return json.dumps(wert, ensure_ascii=False)


def _zeitpunkt(wert):
    return timezone.localtime(wert).isoformat(timespec="seconds")


def _md_linktext(text):
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _md_linkziel(url):
    # Spitze Klammern erlauben Klammern und Leerzeichen im Ziel (CommonMark).
    return "<" + url.replace("<", "%3C").replace(">", "%3E") + ">"


def goal_markdown(goal):
    sessions = list(goal.sessions.all())
    resources = list(goal.resources.all())

    zeilen = [
        "---",
        f"id: {goal.pk}",
        f"title: {_yaml_str(goal.title)}",
        f"status: {_yaml_str(goal.status)}",
        f"created: {_zeitpunkt(goal.created_at)}",
        f"updated: {_zeitpunkt(goal.updated_at)}",
        f"sessions: {len(sessions)}",
        f"total_minutes: {sum(session.duration for session in sessions)}",
        "---",
        "",
        f"# {goal.title}",
        "",
        goal.description.strip() or "_Keine Beschreibung._",
        "",
        "## Ressourcen",
        "",
    ]

    if resources:
        zeilen += [
            f"- [{_md_linktext(r.title)}]({_md_linkziel(r.url)}) -- {r.get_type_display()}"
            for r in resources
        ]
    else:
        zeilen.append("_Keine Ressourcen._")

    zeilen += ["", "## Lernsitzungen", ""]

    if not sessions:
        zeilen.append("_Keine Lernsitzungen._")
    for session in sessions:
        zeilen += [f"### {session.date.isoformat()} -- {session.duration} Min.", ""]
        tags = [tag.name for tag in session.tags.all()]
        if tags:
            zeilen += [f"Tags: {', '.join(tags)}", ""]
        if session.notes.strip():
            zeilen += [session.notes.strip(), ""]

    return "\n".join(zeilen).rstrip("\n") + "\n"


def build_goals_zip(user):
    """ZIP mit einer Markdown-Datei je Goal, als zurueckgespulter Puffer.

    Die Datenmengen eines Nutzers sind klein; das Archiv entsteht im Speicher.
    """
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as archiv:
        for goal in goals_for_export(user):
            archiv.writestr(goal_filename(goal), goal_markdown(goal))
    puffer.seek(0)
    return puffer


# --- JSON-Dump ----------------------------------------------------------------
#
# Alle Felder werden explizit aufgezaehlt (Allowlist) statt per model_to_dict:
# so gelangen Passwort-Hash, is_staff & Co. auch dann nicht in den Export, wenn
# Modelle spaeter wachsen.


def _profile_dict(user):
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        return None
    return {
        "name": profile.name,
        "cohort": profile.cohort,
        "focus_areas": [tag.name for tag in profile.focus_areas.all()],
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _goal_dict(goal):
    return {
        "id": goal.pk,
        "title": goal.title,
        "description": goal.description,
        "status": goal.status,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
        "sessions": [
            {
                "id": session.pk,
                "date": session.date,
                "duration_minutes": session.duration,
                "notes": session.notes,
                "tags": [tag.name for tag in session.tags.all()],
            }
            for session in goal.sessions.all()
        ],
        "resources": [
            {
                "id": resource.pk,
                "title": resource.title,
                "url": resource.url,
                "type": resource.type,
                "created_at": resource.created_at,
            }
            for resource in goal.resources.all()
        ],
        "ai_feedbacks": [
            {
                "id": feedback.pk,
                "feedback_type": feedback.feedback_type,
                "content": feedback.content,
                "created_at": feedback.created_at,
            }
            for feedback in goal.ai_feedbacks.all()
        ],
        "flashcards": [
            {
                "id": karte.pk,
                "question": karte.question,
                "answer": karte.answer,
                "is_mastered": karte.is_mastered,
                "created_at": karte.created_at,
            }
            for karte in goal.flashcards.all()
        ],
    }


def _statistics(goals):
    """Kennzahlen wie im Dashboard, aus den bereits geladenen Daten.

    Eine Sitzung mit mehreren Tags zaehlt -- wie im Dashboard -- in jede ihrer
    Kategorien ein.
    """
    sessions = [session for goal in goals for session in goal.sessions.all()]
    nach_status = Counter(goal.status for goal in goals)
    je_tag = Counter()
    for session in sessions:
        for tag in session.tags.all():
            je_tag[tag.name] += session.duration

    return {
        "goals_total": len(goals),
        "sessions_total": len(sessions),
        "minutes_total": sum(session.duration for session in sessions),
        "goals_by_status": {wert: nach_status[wert] for wert in Goal.Status.values},
        "minutes_by_tag": [
            {"tag": name, "minutes": minuten}
            for name, minuten in sorted(je_tag.items(), key=lambda e: (-e[1], e[0]))
        ],
    }


def build_user_dump(user):
    """Alle eigenen Daten als Dict; serialisierbar mit DjangoJSONEncoder."""
    goals = list(goals_for_export(user).prefetch_related("ai_feedbacks", "flashcards"))
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": timezone.now(),
        "user": {
            "username": user.get_username(),
            "email": user.email,
            "date_joined": user.date_joined,
        },
        "profile": _profile_dict(user),
        "goals": [_goal_dict(goal) for goal in goals],
        "statistics": _statistics(goals),
    }
