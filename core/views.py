from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from core.forms import GoalForm, LearningSessionForm, ProfileForm, RegistrationForm
from core.models import Goal, LearningSession, Profile


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


# --- Profil -----------------------------------------------------------------


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


# --- Goals ------------------------------------------------------------------


class OwnGoalMixin(LoginRequiredMixin):
    """Schraenkt das Queryset generell auf die Goals des angemeldeten Nutzers ein.

    Weil gefiltert statt nachtraeglich geprueft wird, ist ein fremder PK im
    Queryset gar nicht enthalten und get_object() liefert automatisch 404 --
    fuer Detail, Edit und Delete gleichermassen.
    """

    model = Goal

    def get_queryset(self):
        return Goal.objects.filter(user=self.request.user)


class GoalListView(OwnGoalMixin, ListView):
    template_name = "core/goal_list.html"
    context_object_name = "goals"

    def get_status_filter(self):
        """Gibt den angeforderten Status zurueck, sofern er gueltig ist."""
        status = self.request.GET.get("status")
        return status if status in Goal.Status.values else None

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.get_status_filter()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["aktiver_status"] = self.get_status_filter()
        context["status_choices"] = Goal.Status.choices
        return context


class GoalDetailView(OwnGoalMixin, DetailView):
    template_name = "core/goal_detail.html"
    context_object_name = "goal"


class GoalCreateView(LoginRequiredMixin, CreateView):
    model = Goal
    form_class = GoalForm
    template_name = "core/goal_form.html"

    def form_valid(self, form):
        # Zuordnung serverseitig; "user" ist nicht Teil des Formulars.
        form.instance.user = self.request.user
        return super().form_valid(form)


class GoalUpdateView(OwnGoalMixin, UpdateView):
    form_class = GoalForm
    template_name = "core/goal_form.html"


class GoalDeleteView(OwnGoalMixin, DeleteView):
    template_name = "core/goal_confirm_delete.html"
    context_object_name = "goal"
    success_url = reverse_lazy("core:goal_list")


# --- Lernsitzungen ----------------------------------------------------------


class OwnSessionMixin(LoginRequiredMixin):
    """Wie OwnGoalMixin, nur ueber die Beziehung goal__user."""

    model = LearningSession

    def get_queryset(self):
        return LearningSession.objects.filter(
            goal__user=self.request.user
        ).select_related("goal")


class SessionFormUserMixin:
    """Reicht den angemeldeten Nutzer an das Formular durch.

    Der Form schraenkt damit die Goal-Auswahl ein -- auch gegen einen POST mit
    fremder Goal-ID.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class SessionListView(OwnSessionMixin, ListView):
    template_name = "core/learningsession_list.html"
    context_object_name = "sessions"


class SessionDetailView(OwnSessionMixin, DetailView):
    template_name = "core/learningsession_detail.html"
    context_object_name = "session"


class SessionCreateView(LoginRequiredMixin, SessionFormUserMixin, CreateView):
    model = LearningSession
    form_class = LearningSessionForm
    template_name = "core/learningsession_form.html"


class SessionUpdateView(OwnSessionMixin, SessionFormUserMixin, UpdateView):
    form_class = LearningSessionForm
    template_name = "core/learningsession_form.html"


class SessionDeleteView(OwnSessionMixin, DeleteView):
    template_name = "core/learningsession_confirm_delete.html"
    context_object_name = "session"
    success_url = reverse_lazy("core:session_list")
