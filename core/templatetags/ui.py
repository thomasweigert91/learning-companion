"""Darstellungs-Helfer fuer das Bootstrap-UI.

Die Formular-Klassen werden hier vergeben statt per widgets/attrs in forms.py.
So greifen sie auch fuer Django-eigene Formulare wie das AuthenticationForm
des Logins, ohne dass dafuer die URL-Konfiguration angefasst werden muss.
"""

from django import template
from django.urls import reverse

register = template.Library()

# Widget-Typen (BoundField.widget_type) mit abweichender Bootstrap-Klasse;
# alles andere bekommt "form-control".
#
# Checkbox-/Radio-Gruppen (CheckboxSelectMultiple, RadioSelect) fehlen hier
# bewusst: Djangos Gruppen-Template schreibt die class auch auf den aeusseren
# Container-<div>, "form-check-input" wuerde ihn als 1em-Checkbox rendern. Diese
# Gruppen rendert core/_form.html deshalb selbst (field.use_fieldset).
CHECK_WIDGETS = {"checkbox"}
SELECT_WIDGETS = {"select", "selectmultiple", "nullbooleanselect"}

# URL-Namen-Praefix -> Navigationsbereich. Resource-Routen haengen fachlich an
# einem Goal und markieren deshalb den Goals-Bereich.
NAV_SECTIONS = (
    ("dashboard", "dashboard"),
    ("goal", "goals"),
    ("resource", "goals"),
    ("session", "sessions"),
    ("profile", "profile"),
)


def widget_css_class(bound_field):
    widget_type = bound_field.widget_type
    if widget_type in CHECK_WIDGETS:
        return "form-check-input"
    if widget_type in SELECT_WIDGETS:
        return "form-select"
    return "form-control"


@register.filter
def bs_widget(bound_field):
    """Rendert das Widget mit der passenden Bootstrap-Klasse.

    Alles andere kommt unveraendert von Django (BoundField.as_widget): ID, Name,
    Wert, required -- und seit Django 5.2 auch aria-invalid sowie
    aria-describedby mit "<id>_helptext"/"<id>_error". core/_form.html vergibt
    an Hilfe- und Fehlertext genau diese IDs, damit die Verknuepfung greift.
    """
    vorhandene_klasse = bound_field.field.widget.attrs.get("class", "")
    klassen = [vorhandene_klasse, widget_css_class(bound_field)]
    if bound_field.errors:
        klassen.append("is-invalid")
    return bound_field.as_widget(attrs={"class": " ".join(k for k in klassen if k)})


@register.filter
def has_required(form):
    """True, sobald mindestens ein sichtbares Feld Pflicht ist."""
    return any(field.field.required for field in form.visible_fields())


def nav_section(request):
    """Ordnet die aktuelle Route einem Navigationsbereich zu."""
    match = getattr(request, "resolver_match", None)
    url_name = getattr(match, "url_name", None) or ""
    for praefix, section in NAV_SECTIONS:
        if url_name.startswith(praefix):
            return section
    return None


@register.simple_tag(takes_context=True)
def nav_active(context, section):
    """Fuer Elemente ausserhalb von nav_link, z. B. das User-Dropdown."""
    return nav_section(context["request"]) == section


@register.inclusion_tag("core/_nav_link.html", takes_context=True)
def nav_link(context, url_name, label, icon, section):
    """Nav-Link, der sich im aktuellen Bereich als aktiv markiert."""
    return {
        "url": reverse(url_name),
        "label": label,
        "icon": icon,
        "active": nav_section(context["request"]) == section,
    }
