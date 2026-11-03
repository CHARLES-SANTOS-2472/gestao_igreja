import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from membros.models import Member
from ministerios.models import Department
from patrimonio.models import ChurchAsset

TEMP_MEDIA = tempfile.mkdtemp(prefix="gestao-media-imgs-")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ImportImagesTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def test_import_recreates_records_with_images_and_is_idempotent(self):
        call_command("imagens_demo", stdout=StringIO())
        department = Department.objects.get(name="Ministério Infantil")
        self.assertTrue(department.photo.name.startswith("ministerios/"))
        self.assertTrue(ChurchAsset.objects.get(name__startswith="Teclado").photo)
        self.assertTrue(Member.objects.filter(photo__startswith="membros/").exists())
        first = department.photo.name
        call_command("imagens_demo", stdout=StringIO())
        department.refresh_from_db()
        self.assertEqual(department.photo.name, first)
        self.assertEqual(Department.objects.count(), 1)
