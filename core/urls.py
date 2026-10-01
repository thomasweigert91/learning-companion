from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    # Auswertung
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Export (ohne PK: exportiert wird immer request.user)
    path("export/", views.ExportCenterView.as_view(), name="export_center"),
    path(
        "export/sessions.csv",
        views.ExportSessionsCSVView.as_view(),
        name="export_sessions_csv",
    ),
    path("export/goals.zip", views.ExportGoalsZipView.as_view(), name="export_goals_zip"),
    path("export/data.json", views.ExportJSONView.as_view(), name="export_json"),
    # Authentifizierung
    path("accounts/register/", views.RegisterView.as_view(), name="register"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Eigenes Profil (ohne PK: strukturell nicht fremdadressierbar)
    path("profile/", views.ProfileDetailView.as_view(), name="profile_detail"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    # PK-Routen: ueber das gefilterte Queryset abgesichert (fremder PK -> 404)
    path("profile/<int:pk>/", views.ProfileDetailView.as_view(), name="profile_detail_pk"),
    path("profile/<int:pk>/edit/", views.ProfileUpdateView.as_view(), name="profile_edit_pk"),
    # Goals
    path("goals/", views.GoalListView.as_view(), name="goal_list"),
    path("goals/new/", views.GoalCreateView.as_view(), name="goal_create"),
    path("goals/<int:pk>/", views.GoalDetailView.as_view(), name="goal_detail"),
    path("goals/<int:pk>/edit/", views.GoalUpdateView.as_view(), name="goal_edit"),
    path("goals/<int:pk>/delete/", views.GoalDeleteView.as_view(), name="goal_delete"),
    # Lernsitzungen
    path("sessions/", views.SessionListView.as_view(), name="session_list"),
    path("sessions/new/", views.SessionCreateView.as_view(), name="session_create"),
    path("sessions/<int:pk>/", views.SessionDetailView.as_view(), name="session_detail"),
    path("sessions/<int:pk>/edit/", views.SessionUpdateView.as_view(), name="session_edit"),
    path("sessions/<int:pk>/delete/", views.SessionDeleteView.as_view(), name="session_delete"),
    # Ressourcen (pk adressiert beim Anlegen das Goal, beim Loeschen die Resource)
    path(
        "goals/<int:pk>/resources/add/",
        views.ResourceCreateView.as_view(),
        name="resource_create",
    ),
    path(
        "resources/<int:pk>/delete/",
        views.ResourceDeleteView.as_view(),
        name="resource_delete",
    ),
    # KI-Aktionen
    path(
        "goals/<int:pk>/ai/summary/",
        views.GoalSummaryView.as_view(),
        name="goal_ai_summary",
    ),
    path(
        "goals/<int:pk>/ai/next-steps/",
        views.GoalNextStepsView.as_view(),
        name="goal_ai_next_steps",
    ),
    # Lernkarten (pk adressiert beim Generieren das Goal, sonst die Karte)
    path(
        "goals/<int:pk>/ai/flashcards/",
        views.FlashcardGenerateView.as_view(),
        name="goal_ai_flashcards",
    ),
    path(
        "flashcards/<int:pk>/toggle/",
        views.FlashcardToggleView.as_view(),
        name="flashcard_toggle",
    ),
    path(
        "flashcards/<int:pk>/delete/",
        views.FlashcardDeleteView.as_view(),
        name="flashcard_delete",
    ),
    # KI-Historie (pk adressiert beim Zuruecksetzen das Goal, beim Loeschen den Eintrag)
    path(
        "goals/<int:pk>/ai/history/clear/",
        views.AIFeedbackClearView.as_view(),
        name="goal_ai_history_clear",
    ),
    path(
        "ai-feedback/<int:pk>/delete/",
        views.AIFeedbackDeleteView.as_view(),
        name="ai_feedback_delete",
    ),
]
