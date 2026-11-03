import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from eventos.models import ChurchEvent
from membros.models import MessageOccasion
from ministerios.models import Department

TEMP_MEDIA = tempfile.mkdtemp(prefix="gestao-media-demo-")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DemoCommandTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def run_demo(self, *args):
        out = StringIO()
        call_command("carregar_demo", *args, stdout=out)
        return out.getvalue()

    def test_creates_demo_data_with_images_and_is_idempotent(self):
        self.run_demo()
        self.assertEqual(Department.objects.count(), 6)
        self.assertTrue(all(d.photo for d in Department.objects.all()))
        self.assertEqual(ChurchEvent.objects.count(), 3)
        self.assertTrue(MessageOccasion.objects.get(name="Dia das Mães").photo)
        first_photo = Department.objects.get(name="Ministério de Louvor").photo.name
        self.run_demo()
        self.assertEqual(Department.objects.count(), 6)
        self.assertEqual(Department.objects.get(name="Ministério de Louvor").photo.name, first_photo)

    def test_clear_removes_only_demo_data(self):
        Department.objects.create(name="Ministério Real")
        self.run_demo()
        self.run_demo("--limpar")
        self.assertEqual(list(Department.objects.values_list("name", flat=True)), ["Ministério Real"])
        self.assertEqual(ChurchEvent.objects.count(), 0)
        self.assertFalse(MessageOccasion.objects.exclude(photo="").exists())
