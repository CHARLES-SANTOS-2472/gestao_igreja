from django.contrib.auth.models import Group, Permission

ADMIN_GROUP_NAME = "Administrador"

MODULES = (
    ("membros", "Membros e visitantes"),
    ("eventos", "Agenda e reservas"),
    ("ministerios", "Ministérios"),
    ("financeiro", "Financeiro e doações"),
    ("patrimonio", "Patrimônio e tarefas"),
    ("assistencia_social", "Assistência social"),
)
MODULE_APPS = tuple(app for app, _label in MODULES)

LEVEL_NONE = ""
LEVEL_VIEW = "view"
LEVEL_EDIT = "edit"
LEVEL_CHOICES = (
    (LEVEL_NONE, "Sem acesso"),
    (LEVEL_VIEW, "Somente consultar"),
    (LEVEL_EDIT, "Consultar e cadastrar/editar"),
)

_LEVEL_PREFIXES = {
    LEVEL_VIEW: ("view_",),
    LEVEL_EDIT: ("view_", "add_", "change_"),
}


def permissions_for_level(app_label, level):
    prefixes = _LEVEL_PREFIXES.get(level)
    if not prefixes:
        return []
    return [
        permission
        for permission in Permission.objects.filter(
            content_type__app_label=app_label
        )
        if permission.codename.startswith(prefixes)
    ]


def level_for_user_permissions(app_label, user_permissions):
    codenames = {
        permission.codename
        for permission in user_permissions
        if permission.content_type.app_label == app_label
    }
    for level in (LEVEL_EDIT, LEVEL_VIEW):
        required = {
            permission.codename
            for permission in permissions_for_level(app_label, level)
        }
        if required and required <= codenames:
            return level
    return LEVEL_NONE


def ensure_admin_group():
    group, _created = Group.objects.get_or_create(name=ADMIN_GROUP_NAME)
    permissions = Permission.objects.filter(content_type__app_label__in=MODULE_APPS)
    group.permissions.set(permissions)
    return group


def is_administrator(user):
    return user.groups.filter(name=ADMIN_GROUP_NAME).exists()


def can_manage_users(user):
    if not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or is_administrator(user)
