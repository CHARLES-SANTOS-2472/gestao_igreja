from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .access import ADMIN_GROUP_NAME, ensure_admin_group

User = get_user_model()
PASSWORD = "Senha-Forte-2026!"


def form_data(**overrides):
    data = {
        "username": "maria",
        "first_name": "Maria",
        "last_name": "Silva",
        "email": "maria@example.com",
        "role": "common",
        "is_active": "on",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "access_membros": "view",
    }
    data.update(overrides)
    return data


class UserManagementTests(TestCase):
    def setUp(self):
        self.super = User.objects.create_superuser("super", password=PASSWORD)
        self.admin = User.objects.create_user("adm", password=PASSWORD)
        self.admin.groups.add(ensure_admin_group())
        self.common = User.objects.create_user("comum", password=PASSWORD)

    def test_admin_group_exists_with_permissions(self):
        group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.assertTrue(group.permissions.filter(codename="delete_member").exists())

    def test_common_user_gets_403(self):
        self.client.force_login(self.common)
        self.assertEqual(self.client.get(reverse("user-list")).status_code, 403)

    def test_super_creates_common_user_with_view_only(self):
        self.client.force_login(self.super)
        response = self.client.post(reverse("user-create"), form_data())
        self.assertRedirects(response, reverse("user-list"))
        user = User.objects.get(username="maria")
        self.assertTrue(user.has_perm("membros.view_member"))
        self.assertFalse(user.has_perm("membros.add_member"))
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_edit_level_adds_permissions(self):
        self.client.force_login(self.super)
        self.client.post(reverse("user-create"), form_data())
        user = User.objects.get(username="maria")
        data = form_data(access_membros="edit")
        del data["password1"], data["password2"]
        self.client.post(reverse("user-update", args=[user.pk]), data)
        user = User.objects.get(pk=user.pk)
        self.assertTrue(user.has_perm("membros.add_member"))
        self.assertFalse(user.has_perm("membros.delete_member"))

    def test_common_requires_a_module(self):
        self.client.force_login(self.super)
        response = self.client.post(
            reverse("user-create"), form_data(access_membros="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="maria").exists())

    def test_only_super_creates_administrator(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user-create"), form_data(role="admin"))
        self.assertFalse(User.objects.filter(username="maria").exists())
        self.client.force_login(self.super)
        self.client.post(reverse("user-create"), form_data(role="admin"))
        maria = User.objects.get(username="maria")
        self.assertTrue(maria.groups.filter(name=ADMIN_GROUP_NAME).exists())
        self.assertTrue(maria.has_perm("financeiro.delete_financialtransaction"))

    def test_admin_cannot_manage_admins_or_superusers(self):
        other = User.objects.create_user("adm2", password=PASSWORD)
        other.groups.add(ensure_admin_group())
        self.client.force_login(self.admin)
        for target in (other, self.super, self.admin):
            response = self.client.get(reverse("user-update", args=[target.pk]))
            self.assertEqual(response.status_code, 404)

    def test_toggle_active(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user-toggle-active", args=[self.common.pk]))
        self.common.refresh_from_db()
        self.assertFalse(self.common.is_active)
        self.assertEqual(
            self.client.get(reverse("user-toggle-active", args=[self.common.pk])).status_code,
            405,
        )

    def test_reset_password(self):
        self.client.force_login(self.admin)
        new = "Outra-Senha-9087!"
        self.client.post(
            reverse("user-password-reset", args=[self.common.pk]),
            {"new_password1": new, "new_password2": new},
        )
        self.common.refresh_from_db()
        self.assertTrue(self.common.check_password(new))

    def test_own_password_change(self):
        self.client.force_login(self.common)
        new = "Outra-Senha-9087!"
        response = self.client.post(
            reverse("password-change"),
            {"old_password": PASSWORD, "new_password1": new, "new_password2": new},
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )
        self.common.refresh_from_db()
        self.assertTrue(self.common.check_password(new))

    def test_menu_link_only_for_managers(self):
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get(reverse("dashboard")), f'href="{reverse("user-list")}"'
        )
        self.client.force_login(self.common)
        self.common.user_permissions.add(
            *ensure_admin_group().permissions.filter(codename="view_member")
        )
        self.assertNotContains(
            self.client.get(reverse("dashboard")), f'href="{reverse("user-list")}"'
        )
