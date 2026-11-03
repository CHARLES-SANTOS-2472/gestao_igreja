from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import ChurchMessage


class ChurchMessageTests(TestCase):
    def make_user(self, username, codenames):
        user = get_user_model().objects.create_user(username=username, password="SenhaForte#2026")
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        return user

    def test_dashboard_shows_default_verse(self):
        self.client.force_login(self.make_user("leitor", ("view_member",)))
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Não vos lembreis das coisas passadas")
        self.assertContains(response, "Isaías 43:18-19")
        self.assertNotContains(response, "Editar mensagem")

    def test_authorized_user_can_edit_message(self):
        user = self.make_user("secretaria", ("view_member", "change_churchmessage"))
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("dashboard")), "Editar mensagem")

        response = self.client.post(
            reverse("church-message-update"),
            {"title": "Palavra da semana", "text": "O Senhor é o meu pastor.", "reference": "Salmo 23:1"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(ChurchMessage.objects.count(), 1)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Palavra da semana")
        self.assertContains(page, "O Senhor é o meu pastor.")

    def test_user_without_permission_cannot_edit(self):
        self.client.force_login(self.make_user("leitor", ("view_member",)))
        self.assertEqual(self.client.get(reverse("church-message-update")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("church-message-update"), {"title": "x", "text": "y"}).status_code, 403
        )

    def test_html_in_message_is_escaped(self):
        message = ChurchMessage.current()
        message.text = "<script>alert(1)</script>"
        message.save()
        self.client.force_login(self.make_user("leitor", ("view_member",)))
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "<script>alert(1)</script>")
