import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from patrimonio.models import ChurchAsset

from .models import Member

TEMP_MEDIA = tempfile.mkdtemp(prefix="gestao-media-")


def make_image(fmt="PNG", size=(2400, 1800), mode="RGB", name="foto.png"):
    buffer = BytesIO()
    Image.new(mode, size, (200, 30, 40)).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PhotoUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def make_user(self, username, codenames):
        user = get_user_model().objects.create_user(username=username, password="SenhaForte#2026")
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        return user

    def setUp(self):
        self.user = self.make_user(
            "secretaria",
            ("view_member", "add_member", "change_member", "view_churchasset", "add_churchasset", "change_churchasset"),
        )
        self.client.force_login(self.user)

    def post_member(self, **extra):
        data = {"first_name": "Marta", "status": Member.Status.MEMBER, **extra}
        return self.client.post(reverse("member-create"), data)

    def test_member_photo_is_resized_and_served_only_to_authorized_users(self):
        response = self.post_member(photo=make_image())
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Marta")
        self.assertTrue(member.photo.name.startswith("membros/"))
        self.assertTrue(member.photo.name.endswith(".jpg"))
        self.assertNotIn("Marta", member.photo.name)
        with member.photo.open("rb") as stored:
            image = Image.open(stored)
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 1280)

        served = self.client.get(member.photo.url)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/jpeg")
        self.assertEqual(served["X-Content-Type-Options"], "nosniff")
        served.close()

        self.client.logout()
        self.assertEqual(self.client.get(member.photo.url).status_code, 302)
        outsider = self.make_user("sem_permissao", ())
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(member.photo.url).status_code, 403)

    def test_media_view_rejects_traversal_and_unknown_areas(self):
        self.assertEqual(self.client.get("/arquivos/segredo/arquivo.jpg").status_code, 404)
        self.assertEqual(self.client.get("/arquivos/membros/../../db.sqlite3").status_code, 404)
        self.assertEqual(self.client.get("/arquivos/membros/inexistente.jpg").status_code, 404)

    def test_non_image_upload_is_rejected(self):
        fake = SimpleUploadedFile("foto.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
        response = self.post_member(photo=fake)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Member.objects.filter(first_name="Marta").exists())

    def test_transparent_png_is_flattened(self):
        self.post_member(photo=make_image(mode="RGBA", size=(300, 300)))
        member = Member.objects.get(first_name="Marta")
        with member.photo.open("rb") as stored:
            self.assertEqual(Image.open(stored).mode, "RGB")

    def test_replacing_and_removing_photo_deletes_old_file(self):
        self.post_member(photo=make_image(size=(300, 300)))
        member = Member.objects.get(first_name="Marta")
        first_name = member.photo.name
        storage = member.photo.storage

        response = self.client.post(
            reverse("member-update", args=[member.pk]),
            {"first_name": "Marta", "status": Member.Status.MEMBER, "photo": make_image(size=(300, 300))},
        )
        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertNotEqual(member.photo.name, first_name)
        self.assertFalse(storage.exists(first_name))

        second_name = member.photo.name
        self.client.post(
            reverse("member-update", args=[member.pk]),
            {"first_name": "Marta", "status": Member.Status.MEMBER, "remove_photo": "on"},
        )
        member.refresh_from_db()
        self.assertFalse(member.photo)
        self.assertFalse(storage.exists(second_name))

    def test_editing_without_new_file_keeps_photo(self):
        self.post_member(photo=make_image(size=(300, 300)))
        member = Member.objects.get(first_name="Marta")
        kept = member.photo.name
        self.client.post(
            reverse("member-update", args=[member.pk]),
            {"first_name": "Marta Maria", "status": Member.Status.MEMBER},
        )
        member.refresh_from_db()
        self.assertEqual(member.photo.name, kept)

    def test_asset_photo_upload_and_display(self):
        response = self.client.post(
            reverse("asset-create"),
            {
                "name": "Bateria",
                "category": ChurchAsset.Category.INSTRUMENT,
                "status": ChurchAsset.Status.ACTIVE,
                "photo": make_image(size=(800, 600)),
            },
        )
        self.assertEqual(response.status_code, 302)
        asset = ChurchAsset.objects.get(name="Bateria")
        self.assertTrue(asset.photo.name.startswith("patrimonio/"))
        self.assertContains(self.client.get(reverse("asset-detail", args=[asset.pk])), asset.photo.url)
        self.assertContains(self.client.get(reverse("asset-list")), asset.photo.url)

    def test_member_forms_are_multipart(self):
        self.assertContains(self.client.get(reverse("member-create")), 'enctype="multipart/form-data"')
        self.assertContains(self.client.get(reverse("asset-create")), 'enctype="multipart/form-data"')
