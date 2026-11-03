import uuid
from io import BytesIO

from django import forms
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse, Http404
from django.conf import settings
from django.utils._os import safe_join
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1280


def member_photo_path(instance, filename):
    return f"membros/{uuid.uuid4().hex}.jpg"


def asset_photo_path(instance, filename):
    return f"patrimonio/{uuid.uuid4().hex}.jpg"


def department_photo_path(instance, filename):
    return f"ministerios/{uuid.uuid4().hex}.jpg"


def event_photo_path(instance, filename):
    return f"eventos/{uuid.uuid4().hex}.jpg"


def occasion_photo_path(instance, filename):
    return f"ocasioes/{uuid.uuid4().hex}.jpg"


def supplier_photo_path(instance, filename):
    return f"fornecedores/{uuid.uuid4().hex}.jpg"


class PhotoField(forms.ImageField):
    """Valida e regrava a imagem em JPEG reduzido, descartando EXIF (inclusive GPS)."""

    def clean(self, data, initial=None):
        if isinstance(data, UploadedFile) and data.size > MAX_UPLOAD_BYTES:
            raise ValidationError("A foto deve ter no máximo 10 MB.")
        cleaned = super().clean(data, initial)
        if not isinstance(cleaned, UploadedFile):
            return cleaned
        try:
            cleaned.seek(0)
            image = ImageOps.exif_transpose(Image.open(cleaned))
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            buffer = BytesIO()
            image.save(buffer, "JPEG", quality=85, optimize=True)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise ValidationError("Não foi possível ler esta imagem. Envie um arquivo JPG, PNG ou WebP.")
        return ContentFile(buffer.getvalue(), name="foto.jpg")


class PhotoFormMixin(forms.ModelForm):
    photo = PhotoField(
        label="Foto",
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/*"}),
        help_text="No celular, escolha entre tirar uma foto agora ou anexar uma da galeria.",
    )
    remove_photo = forms.BooleanField(label="Remover a foto atual", required=False)
    photo_label = None
    remove_photo_label = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.photo_label:
            self.fields["photo"].label = self.photo_label
        if self.remove_photo_label:
            self.fields["remove_photo"].label = self.remove_photo_label

    def clean(self):
        cleaned_data = super().clean()
        new_photo = cleaned_data.get("photo")
        if cleaned_data.get("remove_photo") and not isinstance(new_photo, ContentFile):
            cleaned_data["photo"] = False
        return cleaned_data


class PhotoModelMixin:
    """Apaga do disco a foto substituída ou removida, e a do registro excluído."""

    def save(self, *args, **kwargs):
        old = ""
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("photo", flat=True).first() or ""
        super().save(*args, **kwargs)
        if old and old != (self.photo.name or ""):
            self.photo.storage.delete(old)

    def delete(self, *args, **kwargs):
        name = self.photo.name
        result = super().delete(*args, **kwargs)
        if name:
            self.photo.storage.delete(name)
        return result


MEDIA_PERMISSIONS = {
    "membros": "membros.view_member",
    "patrimonio": "patrimonio.view_churchasset",
    "ministerios": "ministerios.view_department",
    "eventos": "eventos.view_churchevent",
    "ocasioes": "membros.view_messageoccasion",
    "fornecedores": "patrimonio.view_supplier",
}


@login_required
@require_GET
def protected_media(request, path):
    area = path.split("/", 1)[0]
    permission = MEDIA_PERMISSIONS.get(area)
    if permission is None:
        raise Http404
    if not request.user.has_perm(permission):
        raise PermissionDenied
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
        file = open(full_path, "rb")
    except (SuspiciousFileOperation, ValueError, OSError):
        raise Http404
    response = FileResponse(file, content_type="image/jpeg")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
