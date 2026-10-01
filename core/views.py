from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from core.forms import (
    GoalForm,
    LearningSessionForm,
    ProfileForm,
    RegistrationForm,
    ResourceForm,
)
from core.models import Goal, LearningSession, Profile, Resource
from core.services import ai_service

# Session-Schluessel fuer die fluechtigen KI-Ergebnisse.
AI_SUMMARY_KEY = "ai_summary"
AI_NEXT_STEPS_KEY = "ai_next_steps"


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

    # Wird von ResourceCreateView gesetzt, um im Fehlerfall das ausgefuellte
    # Formular zurueckzugeben, ohne die Detailseite zu duplizieren.
    resource_form = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resource_form"] = self.resource_form or ResourceForm()

        # KI-Ergebnisse nur zeigen, wenn sie zu genau diesem Goal gehoeren --
        # sonst erschiene die Zusammenfassung von Goal A auch unter Goal B.
        gespeichert = self.request.session.get(AI_SUMMARY_KEY)
        if gespeichert and gespeichert.get("goal_id") == self.object.pk:
            context["ai_summary"] = gespeichert.get("text")

        gespeichert = self.request.session.get(AI_NEXT_STEPS_KEY)
        if gespeichert and gespeichert.get("goal_id") == self.object.pk:
            context["ai_next_steps"] = gespeichert.get("steps")

        return context


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

    def get_queryset(self):
        # Die Tabelle zeigt die Tags jeder Session; ohne Prefetch kostete das
        # eine Abfrage pro Zeile.
        return super().get_queryset().prefetch_related("tags")


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


# --- Ressourcen -------------------------------------------------------------


class ResourceCreateView(LoginRequiredMixin, View):
    """Haengt eine Ressource an ein Goal.

    Nur POST: das Formular selbst lebt auf der Goal-Detailseite, ein GET auf
    diese URL haette keinen eigenen Zweck.
    """

    def post(self, request, pk):
        # Das Ziel-Goal kommt aus dem gescopten Queryset, nicht aus dem POST.
        # Ein fremder PK ergibt 404, bevor irgendetwas geschrieben wird.
        goal = get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)

        form = ResourceForm(request.POST)
        if form.is_valid():
            form.instance.goal = goal
            form.save()
            return redirect(goal.get_absolute_url())

        return self.render_detail_with_errors(request, goal, form)

    @staticmethod
    def render_detail_with_errors(request, goal, form):
        """Rendert die Goal-Detailseite mit dem fehlerbehafteten Formular.

        Die Detailseite wird nicht erneut dispatcht -- sie ist eine DetailView
        und wuerde einen POST mit 405 ablehnen. Stattdessen wird ihr Kontext
        wiederverwendet, damit beide Pfade dieselbe Quelle haben und der
        Fehlerfall nicht divergiert, falls die Detailseite spaeter waechst.
        """
        view = GoalDetailView(resource_form=form)
        view.setup(request, pk=goal.pk)
        view.object = goal
        return view.render_to_response(view.get_context_data(object=goal))


class ResourceDeleteView(LoginRequiredMixin, DeleteView):
    model = Resource
    template_name = "core/resource_confirm_delete.html"
    context_object_name = "resource"

    def get_queryset(self):
        return Resource.objects.filter(goal__user=self.request.user).select_related(
            "goal"
        )

    def get_success_url(self):
        return self.object.goal.get_absolute_url()


# --- KI-Aktionen ------------------------------------------------------------


class GoalAIActionMixin(LoginRequiredMixin):
    """Gemeinsamer Ablauf beider KI-Aktionen.

    Nur POST: ein GET laeuft in 405 und loest damit keine Aktion aus.
    """

    session_key = None

    def run_service(self, goal):
        raise NotImplementedError

    def build_result(self, ergebnis, goal):
        raise NotImplementedError

    def post(self, request, pk):
        # Der 404 faellt, bevor irgendein API-Aufruf stattfindet.
        goal = get_object_or_404(Goal.objects.filter(user=request.user), pk=pk)

        try:
            ergebnis = self.run_service(goal)
        except ai_service.AIServiceError as fehler:
            messages.error(request, str(fehler))
        else:
            request.session[self.session_key] = self.build_result(ergebnis, goal)

        return redirect(goal.get_absolute_url())


class GoalSummaryView(GoalAIActionMixin, View):
    session_key = AI_SUMMARY_KEY

    def run_service(self, goal):
        return ai_service.generate_summary(goal)

    def build_result(self, ergebnis, goal):
        return {"goal_id": goal.pk, "text": ergebnis}


class GoalNextStepsView(GoalAIActionMixin, View):
    session_key = AI_NEXT_STEPS_KEY

    def run_service(self, goal):
        return ai_service.suggest_next_steps(goal)

    def build_result(self, ergebnis, goal):
        return {"goal_id": goal.pk, "steps": ergebnis}


# --- Dashboard --------------------------------------------------------------


class DashboardView(LoginRequiredMixin, TemplateView):
    """Aggregierte Auswertung der eigenen Lernaktivitaet.

    Saemtliche Kennzahlen berechnet die Datenbank (Count/Sum), nicht eine
    Schleife in Python. Gefiltert wird konsequent auf den angemeldeten Nutzer:
    Goals ueber user, Sessions ueber goal__user.
    """

    template_name = "core/dashboard.html"

    def get_goals(self):
        return Goal.objects.filter(user=self.request.user)

    def get_sessions(self):
        return LearningSession.objects.filter(goal__user=self.request.user)

    def goals_nach_status(self):
        """Anzahl Goals je Status -- auch ein Status ohne Goals, dann mit 0."""
        gezaehlt = dict(
            self.get_goals().values_list("status").annotate(anzahl=Count("pk"))
        )
        return [
            {"status": wert, "label": label, "anzahl": gezaehlt.get(wert, 0)}
            for wert, label in Goal.Status.choices
        ]

    def zeit_je_tag(self):
        """Lernminuten je Tag-Kategorie.

        tags__isnull=False unterdrueckt die None-Gruppe, die der LEFT JOIN auf
        die M2M-Tabelle fuer Sessions ohne Tag erzeugen wuerde. Eine Session mit
        mehreren Tags zaehlt bewusst in jede ihrer Kategorien ein.
        """
        return list(
            self.get_sessions()
            .filter(tags__isnull=False)
            .values("tags__name")
            .annotate(minuten=Sum("duration"))
            .order_by("-minuten", "tags__name")
        )

    def zeit_je_woche(self):
        """Lernminuten je Kalenderwoche; woche ist jeweils der Montag.

        Das order_by() am Ende ist nicht nur Kosmetik: ohne es zieht
        Meta.ordering = ["-date", "-pk"] das Feld pk in die GROUP-BY-Klausel
        und die Gruppierung zerfaellt in Einzelzeilen.
        """
        return list(
            self.get_sessions()
            .annotate(woche=TruncWeek("date"))
            .values("woche")
            .annotate(minuten=Sum("duration"))
            .order_by("woche")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sessions = self.get_sessions()
        nach_status = self.goals_nach_status()
        je_tag = self.zeit_je_tag()
        je_woche = self.zeit_je_woche()

        context["goals_nach_status"] = nach_status
        context["zeit_je_tag"] = je_tag
        context["zeit_je_woche"] = je_woche

        context["goals_gesamt"] = self.get_goals().count()
        context["sessions_gesamt"] = sessions.count()
        # aggregate() liefert None, solange es keine Sessions gibt.
        context["minuten_gesamt"] = (
            sessions.aggregate(gesamt=Sum("duration"))["gesamt"] or 0
        )

        # Bezugsgroessen fuer die Balkenbreite im Template. default=0 deckt den
        # Fall "keine Daten" ab; bei 0 rendert das Template keinen Balken.
        context["max_status_anzahl"] = max(
            (zeile["anzahl"] for zeile in nach_status), default=0
        )
        context["max_tag_minuten"] = max(
            (zeile["minuten"] for zeile in je_tag), default=0
        )
        context["max_wochen_minuten"] = max(
            (zeile["minuten"] for zeile in je_woche), default=0
        )

        return context
