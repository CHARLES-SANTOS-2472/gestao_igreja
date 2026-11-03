from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

from . import current
from .models import ChangeLog

AUDITED_APPS = {
    "membros", "eventos", "ministerios", "financeiro",
    "patrimonio", "assistencia_social", "contas", "auth",
}
IGNORED_MODELS = {"auditoria.changelog", "auth.permission"}
IGNORED_FIELDS = {"password", "last_login", "updated_at", "created_at"}


def _audited(sender):
    label = sender._meta.label_lower
    return sender._meta.app_label in AUDITED_APPS and label not in IGNORED_MODELS


def _write(instance, action, fields=""):
    user = current.get_user()
    ChangeLog.objects.create(
        user=user,
        username=user.get_username() if user else "",
        action=action,
        app_label=instance._meta.app_label,
        model_name=str(instance._meta.verbose_name).capitalize(),
        object_id=str(instance.pk or ""),
        object_repr=str(instance)[:200],
        changed_fields=fields[:500],
    )


def _changed_fields(instance):
    old = type(instance)._default_manager.filter(pk=instance.pk).first()
    if old is None:
        return ""
    names = []
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        if getattr(old, field.attname) != getattr(instance, field.attname):
            names.append(str(field.verbose_name))
    return ", ".join(names)


def _before_save(sender, instance, raw=False, **kwargs):
    if raw or not _audited(sender) or instance.pk is None:
        return
    instance._audit_changed = _changed_fields(instance)


def _after_save(sender, instance, created, raw=False, **kwargs):
    if raw or not _audited(sender):
        return
    if created:
        _write(instance, ChangeLog.CREATED)
        return
    changed = getattr(instance, "_audit_changed", "")
    if changed:
        _write(instance, ChangeLog.UPDATED, changed)


def _after_delete(sender, instance, **kwargs):
    if _audited(sender):
        _write(instance, ChangeLog.DELETED)


for model in apps.get_models():
    if model._meta.app_label in AUDITED_APPS:
        pre_save.connect(_before_save, sender=model, weak=False)
        post_save.connect(_after_save, sender=model, weak=False)
        post_delete.connect(_after_delete, sender=model, weak=False)
