from django.apps import AppConfig


class ComunicacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comunicacao"
    verbose_name = "Comunicação"

    def ready(self):
        from . import signals  # noqa: F401
