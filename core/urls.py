from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
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
]
