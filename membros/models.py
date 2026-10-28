from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class CboOccupation(models.Model):
    code = models.CharField("código CBO", max_length=6, primary_key=True)
    title = models.CharField("ocupação", max_length=180)

    class Meta:
        ordering = ["title", "code"]
        verbose_name = "ocupação CBO"
        verbose_name_plural = "ocupações CBO"

    def __str__(self):
        return f"{self.code} — {self.title}"


class MessageOccasion(models.Model):
    name = models.CharField("ocasião", max_length=100)
    month = models.PositiveSmallIntegerField("mês")
    day = models.PositiveSmallIntegerField("dia")
    ai_guidance = models.TextField(
        "orientação para a mensagem", blank=True,
        help_text="Contexto opcional para a IA criar a mensagem desta ocasião.",
    )
    whatsapp_template_name = models.CharField(
        "modelo aprovado no WhatsApp", max_length=100, blank=True
    )
    active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["month", "day", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "month", "day"],
                name="unique_message_occasion_per_date",
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1, month__lte=12, day__gte=1, day__lte=31),
                name="message_occasion_month_day_range",
            ),
        ]
        verbose_name = "ocasião de mensagem"
        verbose_name_plural = "ocasiões de mensagens"

    def clean(self):
        super().clean()
        try:
            date(2000, self.month, self.day)
        except (TypeError, ValueError):
            raise ValidationError({"day": "Informe um dia válido para o mês escolhido."})

    def __str__(self):
        return f"{self.name} ({self.day:02d}/{self.month:02d})"


class Member(models.Model):
    class Status(models.TextChoices):
        MEMBER = "member", "Membro"
        CONGREGANT = "congregant", "Congregado"
        VISITOR = "visitor", "Visitante"
        NEW_CONVERT = "new_convert", "Novo convertido"
        TRANSFERRED = "transferred", "Transferido"
        INACTIVE = "inactive", "Inativo"
        PENDING = "pending", "Cadastro familiar incompleto"

    first_name = models.CharField("nome", max_length=100)
    last_name = models.CharField("sobrenome", max_length=150, blank=True)
    is_placeholder = models.BooleanField("cadastro familiar incompleto", default=False)
    is_deceased = models.BooleanField("falecido(a) (in memoriam)", default=False)
    deceased_on = models.DateField("data de falecimento", null=True, blank=True)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    rg = models.CharField("RG", max_length=30, blank=True)
    birth_date = models.DateField("data de nascimento", null=True, blank=True)
    cbo_occupation = models.ForeignKey(
        CboOccupation,
        verbose_name="ocupação CBO",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    profession = models.CharField(
        "outra profissão (fora da CBO)", max_length=100, blank=True
    )
    landline = models.CharField("telefone fixo", max_length=30, blank=True)
    mobile = models.CharField("celular / WhatsApp", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    postal_code = models.CharField("CEP", max_length=10, blank=True)
    street = models.CharField("logradouro", max_length=150, blank=True)
    number = models.CharField("número", max_length=20, blank=True)
    address_extra = models.CharField("complemento", max_length=100, blank=True)
    neighborhood = models.CharField("bairro", max_length=100, blank=True)
    city = models.CharField("cidade", max_length=100, blank=True)
    state = models.CharField("UF", max_length=2, blank=True)
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.MEMBER
    )
    joined_on = models.DateField("data de entrada", null=True, blank=True)
    baptized_on = models.DateField("data do batismo", null=True, blank=True)
    baptized_at = models.CharField("igreja onde foi batizado", max_length=180, blank=True)
    spouse = models.ForeignKey(
        "self",
        verbose_name="cônjuge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spouse_links",
    )
    parents = models.ManyToManyField(
        "self",
        verbose_name="pais/responsáveis",
        through="FamilyRelationship",
        through_fields=("child", "parent"),
        symmetrical=False,
        related_name="children",
        blank=True,
    )
    email_consent = models.BooleanField("autorizou contato por e-mail", default=False)
    whatsapp_consent = models.BooleanField("autorizou contato por WhatsApp", default=False)
    whatsapp_consent_at = models.DateTimeField(
        "autorização para contato por WhatsApp registrada em", null=True, blank=True
    )
    whatsapp_revoked_at = models.DateTimeField(
        "autorização para contato por WhatsApp revogada em", null=True, blank=True
    )
    whatsapp_daily_consent = models.BooleanField(
        "autorizou mensagens diárias por WhatsApp", default=False
    )
    whatsapp_daily_consent_at = models.DateTimeField(
        "autorização para mensagens diárias registrada em", null=True, blank=True
    )
    whatsapp_daily_revoked_at = models.DateTimeField(
        "autorização para mensagens diárias revogada em", null=True, blank=True
    )
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        permissions = [
            ("view_pastoral_member_data", "Pode acessar dados pastorais restritos"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(whatsapp_daily_consent=False) | Q(whatsapp_consent=True),
                name="daily_whatsapp_requires_contact_consent",
            ),
        ]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        if self.is_placeholder:
            return f"{full_name} (cadastro incompleto)"
        return full_name

    def clean(self):
        super().clean()
        if self.whatsapp_daily_consent and not self.whatsapp_consent:
            raise ValidationError(
                {"whatsapp_daily_consent": "Autorize também o contato geral por WhatsApp."}
            )
        if self.whatsapp_daily_consent and not self.mobile.strip():
            raise ValidationError(
                {"whatsapp_daily_consent": "Informe um celular antes de autorizar mensagens diárias."}
            )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        changed_fields = set(update_fields or ())
        consent_fields = ("whatsapp_consent", "whatsapp_daily_consent")
        previous = {}
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values(*consent_fields).first() or {}
            )

        for field, stamp, revoked in (
            ("whatsapp_consent", "whatsapp_consent_at", "whatsapp_revoked_at"),
            (
                "whatsapp_daily_consent",
                "whatsapp_daily_consent_at",
                "whatsapp_daily_revoked_at",
            ),
        ):
            if update_fields is not None and field not in update_fields:
                continue
            old_value = previous.get(field, False)
            new_value = getattr(self, field)
            if new_value == old_value:
                continue
            if new_value:
                setattr(self, stamp, timezone.now())
                setattr(self, revoked, None)
            elif old_value:
                setattr(self, revoked, timezone.now())
            changed_fields.update((stamp, revoked))
        if update_fields is not None:
            kwargs["update_fields"] = changed_fields
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        address = " ".join(part for part in (self.street, self.number) if part)
        if self.address_extra:
            address = f"{address}, {self.address_extra}" if address else self.address_extra
        location = " - ".join(part for part in (self.neighborhood, self.city) if part)
        if self.state:
            location = f"{location}/{self.state}" if location else self.state
        return ", ".join(part for part in (address, location, self.postal_code) if part)


class FamilyRelationship(models.Model):
    parent = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="parent_relationships"
    )
    child = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="child_relationships"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "child"], name="unique_parent_child_relationship"
            ),
            models.CheckConstraint(
                condition=~Q(parent=F("child")), name="family_relationship_no_self_link"
            ),
        ]
        verbose_name = "vínculo familiar"
        verbose_name_plural = "vínculos familiares"

    def clean(self):
        if self.parent_id == self.child_id:
            raise ValidationError("Uma pessoa não pode ser vinculada como seu próprio responsável.")
