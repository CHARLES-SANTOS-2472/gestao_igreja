import tempfile
import zipfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from membros.models import Member

from .models import ChangeLog
from . import current


class ChangeLogTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("chefe", "c@x.com", "senha-Forte-123")
        ChangeLog.objects.all().delete()

    def test_records_create_update_delete_without_values(self):
        member = Member.objects.create(first_name="Ana", last_name="Silva", cpf="123.456.789-09")
        member.first_name = "Anita"
        member.save()
        member.delete()
        actions = list(ChangeLog.objects.order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, ["created", "updated", "deleted"])
        update = ChangeLog.objects.get(action="updated")
        self.assertIn("nome", update.changed_fields)
        self.assertNotIn("Anita", update.changed_fields)

    def test_unchanged_save_not_logged(self):
        member = Member.objects.create(first_name="Ana", last_name="Silva")
        member.save()
        self.assertEqual(ChangeLog.objects.count(), 1)

    def test_records_user_from_context(self):
        token = current.set_user(self.admin)
        try:
            Member.objects.create(first_name="Ana", last_name="Silva")
        finally:
            current.reset(token)
        self.assertEqual(ChangeLog.objects.get().username, "chefe")

    def test_list_restricted_to_administrators(self):
        url = reverse("changelog-list")
        self.assertEqual(self.client.get(url).status_code, 302)
        common = get_user_model().objects.create_user("comum", password="senha-Forte-123")
        self.client.force_login(common)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url, {"acao": "created"}).status_code, 200)


class BackupTests(TestCase):
    def test_backup_and_keep_limit(self):
        Member.objects.create(first_name="Ana", last_name="Silva")
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as media:
            (Path(media) / "membros").mkdir()
            (Path(media) / "membros" / "a.jpg").write_bytes(b"x")
            with override_settings(MEDIA_ROOT=media):
                for _ in range(3):
                    call_command("backup", pasta=folder, manter=2, stdout=StringIO())
                    import time
                    time.sleep(1.1)
            files = sorted(Path(folder).glob("backup-*.zip"))
            self.assertEqual(len(files), 2)
            with zipfile.ZipFile(files[-1]) as archive:
                self.assertIn("dados.json", archive.namelist())
                self.assertIn("media/membros/a.jpg", archive.namelist())
