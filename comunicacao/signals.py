from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from membros.models import Member


@receiver(post_save, sender=Member)
def send_welcome_after_signup(sender, instance, created, raw=False, **kwargs):
    if not created or raw or instance.is_placeholder:
        return
    from .services import welcome_member

    transaction.on_commit(lambda: welcome_member(instance.pk))
