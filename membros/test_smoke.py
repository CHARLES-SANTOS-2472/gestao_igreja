from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import get_resolver, reverse


class SmokeTests(TestCase):
    """Abre todas as telas sem parâmetros como administrador e confere que nenhuma quebra."""

    def test_all_parameterless_pages_open(self):
        admin = get_user_model().objects.create_superuser("chefe", "c@x.com", "senha-Forte-123")
        self.client.force_login(admin)
        skip = {"logout", "admin"}
        failures = []
        for name in set(get_resolver().reverse_dict.keys()):
            if not isinstance(name, str) or name in skip or name.startswith("admin"):
                continue
            try:
                url = reverse(name)
            except Exception:
                continue
            if url.startswith("/admin/") or url.startswith("/sair/"):
                continue
            response = self.client.get(url)
            if response.status_code >= 400:
                failures.append((name, url, response.status_code))
        self.assertEqual(failures, [])
