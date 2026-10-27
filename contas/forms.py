from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .access import (
    ADMIN_GROUP_NAME,
    LEVEL_CHOICES,
    LEVEL_NONE,
    MODULES,
    ensure_admin_group,
    is_administrator,
    level_for_user_permissions,
    permissions_for_level,
)

User = get_user_model()

ROLE_COMMON = "common"
ROLE_ADMIN = "admin"


class ManagedUserForm(forms.Form):
    username = forms.CharField(label="Usuário (login)", max_length=150)
    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)
    role = forms.ChoiceField(label="Perfil", choices=())
    is_active = forms.BooleanField(label="Usuário ativo", required=False, initial=True)
    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
    )
    password2 = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
    )

    def __init__(self, *args, actor, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.instance = instance
        roles = [(ROLE_COMMON, "Usuário comum (acesso escolhido abaixo)")]
        if actor.is_superuser:
            roles.insert(
                0, (ROLE_ADMIN, "Administrador (acesso total e gestão de usuários)")
            )
        self.fields["role"].choices = roles
        self.fields["role"].initial = ROLE_COMMON
        for app_label, label in MODULES:
            self.fields[self.module_field(app_label)] = forms.ChoiceField(
                label=label, choices=LEVEL_CHOICES, required=False
            )
        if instance is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            del self.fields["password1"]
            del self.fields["password2"]
            if not self.is_bound:
                self.initial.update(self._initial_from(instance))

    @staticmethod
    def module_field(app_label):
        return f"access_{app_label}"

    @property
    def module_fields(self):
        return [self[self.module_field(app_label)] for app_label, _label in MODULES]

    def _initial_from(self, user):
        permissions = list(user.user_permissions.select_related("content_type"))
        initial = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_active": user.is_active,
            "role": ROLE_ADMIN if is_administrator(user) else ROLE_COMMON,
        }
        for app_label, _label in MODULES:
            initial[self.module_field(app_label)] = level_for_user_permissions(
                app_label, permissions
            )
        return initial

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        existing = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Já existe um usuário com este login.")
        return username

    def clean(self):
        cleaned = super().clean()
        if self.instance is None:
            password1 = cleaned.get("password1")
            password2 = cleaned.get("password2")
            if password1 and password2 and password1 != password2:
                self.add_error("password2", "As senhas não conferem.")
            elif password1:
                candidate = User(
                    username=cleaned.get("username", ""),
                    first_name=cleaned.get("first_name", ""),
                    email=cleaned.get("email", ""),
                )
                try:
                    validate_password(password1, candidate)
                except forms.ValidationError as error:
                    self.add_error("password1", error)
        if cleaned.get("role") == ROLE_COMMON and not any(
            cleaned.get(self.module_field(app_label)) for app_label, _l in MODULES
        ):
            raise forms.ValidationError(
                "Escolha o acesso a pelo menos um módulo para o usuário comum."
            )
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = self.instance or User()
        user.username = data["username"]
        user.first_name = data["first_name"]
        user.last_name = data.get("last_name", "")
        user.email = data.get("email", "")
        user.is_active = data.get("is_active", False)
        user.is_staff = False
        user.is_superuser = False
        if self.instance is None:
            user.set_password(data["password1"])
        user.save()

        if data["role"] == ROLE_ADMIN and self.actor.is_superuser:
            user.groups.set([ensure_admin_group()])
            user.user_permissions.clear()
        else:
            user.groups.remove(*user.groups.filter(name=ADMIN_GROUP_NAME))
            permissions = []
            for app_label, _label in MODULES:
                permissions.extend(
                    permissions_for_level(
                        app_label, data.get(self.module_field(app_label), LEVEL_NONE)
                    )
                )
            user.user_permissions.set(permissions)
        return user
