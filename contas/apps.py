from django.apps import AppConfig
from django.db.models.signals import post_migrate


def sync_admin_group(sender, **kwargs):
    from .access import ensure_admin_group

    ensure_admin_group()


class ContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"
    verbose_name = "Usuários e acessos"

    def ready(self):
        post_migrate.connect(sync_admin_group)
