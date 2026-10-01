from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from core.models import Profile

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
