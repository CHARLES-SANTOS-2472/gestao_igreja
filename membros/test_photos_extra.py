import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from eventos.models import ChurchEvent
from ministerios.models import Department
from patrimonio.models import Supplier

from .models import MessageOccasion
from .test_photos import make_image

TEMP_MEDIA = tempfile.mkdtemp(prefix="gestao-media-extra-")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ExtraPhotoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def make_user(self, username, codenames):
        user = get_user_model().objects.create_user(username=username, password="senha-de-teste-123")
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        return user

    def setUp(self):
        self.client.force_login(self.make_user("adm", (
            "view_department", "add_department", "change_department",
            "view_churchevent", "add_churchevent", "change_churchevent",
            "view_supplier", "add_supplier", "change_supplier",
            "view_messageoccasion", "add_messageoccasion", "change_messageoccasion",
        )))

    def assert_protected(self, instance, codename_for_denied):
        url = instance.photo.url
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.make_user("sem-permissao", (codename_for_denied,)))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_department_image(self):
        response = self.client.post(
            reverse("department-create"),
            {"name": "Louvor", "active": "on", "photo": make_image()},
        )
        self.assertEqual(response.status_code, 302)
        department = Department.objects.get(name="Louvor")
        self.assertTrue(department.photo.name.startswith("ministerios/"))
        self.assertContains(self.client.get(reverse("department-list")), department.photo.url)
        self.assert_protected(department, "view_member")

    def test_department_image_can_be_removed(self):
        department = Department.objects.create(name="Jovens")
        self.client.post(
            reverse("department-update", args=[department.pk]),
            {"name": "Jovens", "active": "on", "photo": make_image()},
        )
        department.refresh_from_db()
        self.assertTrue(department.photo)
        self.client.post(
            reverse("department-update", args=[department.pk]),
            {"name": "Jovens", "active": "on", "remove_photo": "on"},
        )
        department.refresh_from_db()
        self.assertFalse(department.photo)

    def test_event_poster(self):
        start = timezone.now() + timedelta(days=3)
        response = self.client.post(
            reverse("event-create"),
            {
                "title": "Congresso", "kind": "congress", "status": "draft",
                "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
                "ends_at": (start + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
                "photo": make_image(),
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        event = ChurchEvent.objects.get(title="Congresso")
        self.assertTrue(event.photo.name.startswith("eventos/"))
        self.assertContains(self.client.get(reverse("event-detail", args=[event.pk])), event.photo.url)
        self.assert_protected(event, "view_member")

    def test_supplier_logo(self):
        response = self.client.post(
            reverse("supplier-create"),
            {"name": "Som & Luz", "active": "on", "photo": make_image()},
        )
        self.assertEqual(response.status_code, 302)
        supplier = Supplier.objects.get(name="Som & Luz")
        self.assertTrue(supplier.photo.name.startswith("fornecedores/"))
        self.assert_protected(supplier, "view_member")

    def test_occasion_image_and_banner(self):
        response = self.client.post(
            reverse("occasion-create"),
            {"name": "Dia do Músico", "month": 11, "day": 22, "active": "on", "photo": make_image()},
        )
        self.assertEqual(response.status_code, 302)
        occasion = MessageOccasion.objects.get(name="Dia do Músico")
        self.assertTrue(occasion.photo.name.startswith("ocasioes/"))
        self.assertContains(self.client.get(reverse("occasion-list")), occasion.photo.url)
        self.assert_protected(occasion, "view_member")

        from comunicacao.services import build_banner

        png = build_banner("Dia do Músico", "Texto", "Verso", "Salmos 1:1", occasion.photo.path)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_invalid_file_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(
            reverse("department-create"),
            {"name": "X", "active": "on", "photo": SimpleUploadedFile("a.png", b"nao-e-imagem", "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Department.objects.filter(name="X").exists())
