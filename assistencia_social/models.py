from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class AssistedFamily(models.Model):
    reference_name = models.CharField("identificação da família", max_length=160)
    contact_name = models.CharField("pessoa de contato", max_length=160, blank=True)
    phone = models.CharField("telefone de contato", max_length=30, blank=True)
    postal_code = models.CharField("CEP", max_length=10, blank=True)
    street = models.CharField("logradouro", max_length=150, blank=True)
    number = models.CharField("número", max_length=20, blank=True)
    address_extra = models.CharField("complemento", max_length=100, blank=True)
    neighborhood = models.CharField("bairro", max_length=120, blank=True)
    city = models.CharField("cidade", max_length=100, blank=True)
    state = models.CharField("UF", max_length=2, blank=True)
    address = models.CharField(
        "endereço informado anteriormente", max_length=240, blank=True
    )
    household_size = models.PositiveSmallIntegerField(
        "pessoas no domicílio",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    active = models.BooleanField("em acompanhamento", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cadastrada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assisted_families_created",
    )
    created_at = models.DateTimeField("cadastrada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["reference_name"]
        verbose_name = "família atendida"
        verbose_name_plural = "famílias atendidas"

    def __str__(self):
        return self.reference_name

    @property
    def formatted_address(self):
        street = " ".join(part for part in (self.street, self.number) if part)
        if self.address_extra:
            street = (
                f"{street}, {self.address_extra}" if street else self.address_extra
            )
        location = ", ".join(
            part for part in (self.neighborhood, self.city) if part
        )
        if self.state:
            location = f"{location}/{self.state}" if location else self.state
        structured_address = ", ".join(
            part for part in (street, location, self.postal_code) if part
        )
        return structured_address if self.street or not self.address else self.address


class AssistanceRecord(models.Model):
    class AidType(models.TextChoices):
        FOOD_BASKET = "food_basket", "Cesta básica"
        FOOD = "food", "Alimentos"
        HYGIENE = "hygiene", "Itens de higiene"
        CLOTHING = "clothing", "Roupas"
        FINANCIAL = "financial", "Ajuda financeira"
        OTHER = "other", "Outra ajuda"

    class Status(models.TextChoices):
        PLANNED = "planned", "Programada"
        DELIVERED = "delivered", "Entregue"
        CANCELLED = "cancelled", "Cancelada"

    family = models.ForeignKey(
        AssistedFamily,
        verbose_name="família",
        on_delete=models.PROTECT,
        related_name="assistance_records",
    )
    aid_type = models.CharField("tipo de ajuda", max_length=20, choices=AidType.choices)
    description = models.CharField("descrição objetiva", max_length=180, blank=True)
    quantity = models.PositiveSmallIntegerField(
        "quantidade",
        default=1,
        validators=[MinValueValidator(1)],
    )
    amount = models.DecimalField(
        "valor da ajuda financeira",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    assistance_date = models.DateField("data programada / realizada")
    status = models.CharField(
        "situação", max_length=12, choices=Status.choices, default=Status.PLANNED
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_assistance_records_created",
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="entregue por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_assistance_records_delivered",
    )
    created_at = models.DateTimeField("registrada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["-assistance_date", "-created_at"]
        verbose_name = "registro de assistência"
        verbose_name_plural = "registros de assistência"
        indexes = [
            models.Index(
                fields=["status", "assistance_date"], name="assist_status_date_idx"
            )
        ]

    def __str__(self):
        return f"{self.get_aid_type_display()} — {self.family}"

    def clean(self):
        super().clean()
        if self.aid_type == self.AidType.FINANCIAL and self.amount is None:
            raise ValidationError(
                {"amount": "Informe o valor para registrar uma ajuda financeira."}
            )
        if self.aid_type != self.AidType.FINANCIAL and self.amount is not None:
            raise ValidationError(
                {"amount": "Informe valor somente para ajuda financeira."}
            )

    def save(self, *args, **kwargs):
        if self.status != self.Status.DELIVERED:
            self.delivered_by = None
        super().save(*args, **kwargs)
