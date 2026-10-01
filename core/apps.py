from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Erst hier importieren, damit die App-Registry vollstaendig geladen ist.
        import core.signals  # noqa: F401
