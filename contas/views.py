from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from .access import ADMIN_GROUP_NAME, can_manage_users, is_administrator
from .forms import ManagedUserForm

User = get_user_model()


class UserManagerMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_manage_users(self.request.user)

    def manageable_users(self):
        queryset = User.objects.filter(is_superuser=False).exclude(
            pk=self.request.user.pk
        )
        if not self.request.user.is_superuser:
            queryset = queryset.exclude(groups__name=ADMIN_GROUP_NAME)
        return queryset

    def get_target(self, pk):
        return get_object_or_404(self.manageable_users(), pk=pk)


class UserListView(UserManagerMixin, TemplateView):
    template_name = "contas/user_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        manageable_ids = set(self.manageable_users().values_list("pk", flat=True))
        rows = []
        for user in User.objects.order_by("first_name", "username"):
            if user.is_superuser:
                role = "Super administrador"
            elif is_administrator(user):
                role = "Administrador"
            else:
                role = "Usuário comum"
            rows.append(
                {
                    "user": user,
                    "role": role,
                    "can_manage": user.pk in manageable_ids,
                    "is_self": user.pk == self.request.user.pk,
                }
            )
        context["rows"] = rows
        return context


class UserCreateView(UserManagerMixin, FormView):
    template_name = "contas/user_form.html"
    form_class = ManagedUserForm
    success_url = reverse_lazy("user-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(form_title="Novo usuário", creating=True)
        return context

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f"Usuário {user.username} cadastrado.")
        return super().form_valid(form)


class UserUpdateView(UserManagerMixin, FormView):
    template_name = "contas/user_form.html"
    form_class = ManagedUserForm
    success_url = reverse_lazy("user-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        kwargs["instance"] = self.get_target(self.kwargs["pk"])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            form_title="Editar usuário",
            creating=False,
            target=self.get_target(self.kwargs["pk"]),
        )
        return context

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f"Usuário {user.username} atualizado.")
        return super().form_valid(form)


class UserPasswordResetView(UserManagerMixin, FormView):
    template_name = "contas/user_password.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("user-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_target(self.kwargs["pk"])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target"] = self.get_target(self.kwargs["pk"])
        return context

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f"Nova senha definida para {user.username}.")
        return super().form_valid(form)


class UserToggleActiveView(UserManagerMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        user = self.get_target(pk)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "ativado" if user.is_active else "desativado"
        messages.success(request, f"Usuário {user.username} {state}.")
        return redirect("user-list")


class OwnPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "contas/password_change.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Sua senha foi alterada.")
        return super().form_valid(form)
