from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auditoria"
    verbose_name = "Histórico de alterações"

    def ready(self):
        from . import signals  # noqa: F401
