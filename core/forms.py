from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from core.models import Goal, LearningSession, Profile, Resource

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """Registrierung auf Basis des Django-Standardformulars.

    Passwort-Hashing und Passwort-Validierung kommen damit unveraendert aus
    django.contrib.auth.
    """

    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["name", "cohort", "focus_areas"]
        widgets = {"focus_areas": forms.CheckboxSelectMultiple()}
        labels = {
            "name": "Name",
            "cohort": "Cohort",
            "focus_areas": "Focus Areas",
        }


class GoalForm(forms.ModelForm):
    """Formular fuer Goals.

    "user" ist bewusst kein Feld: die Zuordnung setzt die View serverseitig aus
    request.user, damit sie nicht per POST ueberschrieben werden kann.
    """

    class Meta:
        model = Goal
        fields = ["title", "description", "status"]
        labels = {
            "title": "Titel",
            "description": "Beschreibung",
            "status": "Status",
        }


class LearningSessionForm(forms.ModelForm):
    """Formular fuer Lernsitzungen.

    Das Queryset von "goal" wird auf die Goals des uebergebenen Nutzers
    eingeschraenkt. Das begrenzt nicht nur die Auswahl im Dropdown, sondern
    laesst einen POST mit fremder Goal-ID serverseitig als ungueltige Auswahl
    auflaufen.
    """

    class Meta:
        model = LearningSession
        fields = ["goal", "date", "duration", "notes", "tags"]
        widgets = {
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "tags": forms.CheckboxSelectMultiple(),
        }
        labels = {
            "goal": "Lernziel",
            "date": "Datum",
            "duration": "Dauer (Minuten)",
            "notes": "Notizen",
            "tags": "Tags",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["goal"].queryset = Goal.objects.filter(user=user)


class ResourceForm(forms.ModelForm):
    """Formular zum Anhaengen einer Ressource an ein Goal.

    "goal" ist bewusst kein Feld: Das Ziel-Goal bestimmt die View aus der URL
    gegen das auf request.user gescopte Queryset und ist damit nicht per POST
    ueberschreibbar.
    """

    class Meta:
        model = Resource
        fields = ["url", "title", "type"]
        widgets = {
            "url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }
        labels = {
            "url": "URL",
            "title": "Titel",
            "type": "Typ",
        }
