from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from core.forms import ProfileForm, RegistrationForm
from core.models import Profile


class HomeView(TemplateView):
    """Oeffentliche Startseite."""

    template_name = "core/home.html"


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("core:profile_detail")

    def form_valid(self, form):
        # Das Profil entsteht per post_save-Signal, sobald der User gespeichert ist.
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class OwnProfileMixin(LoginRequiredMixin):
    """Beschraenkt jeden Zugriff auf das Profil des angemeldeten Nutzers.

    Das Queryset ist grundsaetzlich auf request.user eingeschraenkt. Damit
    liefert die PK-Route fuer ein fremdes Profil automatisch 404, und die
    Routen ohne PK koennen gar kein fremdes Profil adressieren.
    """

    model = Profile
    context_object_name = "profile"

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        if self.kwargs.get(self.pk_url_kwarg) is not None:
            # PK aus der URL: greift das gefilterte Queryset -> fremder PK = 404.
            return super().get_object(queryset)
        return get_object_or_404(queryset, user=self.request.user)


class ProfileDetailView(OwnProfileMixin, DetailView):
    template_name = "core/profile_detail.html"


class ProfileUpdateView(OwnProfileMixin, UpdateView):
    form_class = ProfileForm
    template_name = "core/profile_form.html"
    # Kein success_url: das Ziel kommt aus Profile.get_absolute_url().
