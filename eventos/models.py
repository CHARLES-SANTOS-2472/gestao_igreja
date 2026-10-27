from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from membros.models import Member


class ChurchEvent(models.Model):
    class Kind(models.TextChoices):
        SERVICE = "service", "Culto"
        CONGRESS = "congress", "Congresso"
        VIGIL = "vigil", "Vigília"
        RETREAT = "retreat", "Retiro"
        CONFERENCE = "conference", "Conferência"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        CANCELLED = "cancelled", "Cancelado"

    title = models.CharField("título", max_length=160)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices, default=Kind.SERVICE)
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    description = models.TextField("descrição", blank=True)
    starts_at = models.DateTimeField("início")
    ends_at = models.DateTimeField("término")
    location = models.CharField("local", max_length=180, blank=True)
    registration_open = models.BooleanField("inscrições abertas", default=False)
    capacity = models.PositiveIntegerField("limite de participantes", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cadastrado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_events_created",
    )
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["starts_at", "title"]
        verbose_name = "evento"
        verbose_name_plural = "eventos"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "O término deve ser posterior ao início."})


class EventProgramItem(models.Model):
    event = models.ForeignKey(
        ChurchEvent, on_delete=models.CASCADE, related_name="program_items"
    )
    title = models.CharField("atividade", max_length=160)
    starts_at = models.DateTimeField("horário")
    details = models.CharField("observações", max_length=240, blank=True)
    position = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        ordering = ["starts_at", "position", "pk"]
        verbose_name = "item da programação"
        verbose_name_plural = "itens da programação"

    def __str__(self):
        return f"{self.event}: {self.title}"

    def clean(self):
        super().clean()
        if self.event_id and self.starts_at:
            if not self.event.starts_at <= self.starts_at <= self.event.ends_at:
                raise ValidationError(
                    {"starts_at": "O horário da atividade deve ficar dentro do período do evento."}
                )


class EventAssignment(models.Model):
    class Role(models.TextChoices):
        PREACHER = "preacher", "Pregador"
        LEADER = "leader", "Dirigente"
        MUSICIAN = "musician", "Músico"
        RECEPTION = "reception", "Recepção"
        TEAM = "team", "Equipe de apoio"
        OTHER = "other", "Outro"

    event = models.ForeignKey(
        ChurchEvent, on_delete=models.CASCADE, related_name="assignments"
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="event_assignments"
    )
    role = models.CharField("função", max_length=20, choices=Role.choices)
    notes = models.CharField("observações", max_length=240, blank=True)

    class Meta:
        ordering = ["role", "member__first_name", "member__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member", "role"], name="unique_event_member_role"
            )
        ]
        verbose_name = "escala de serviço"
        verbose_name_plural = "escalas de serviço"

    def __str__(self):
        return f"{self.member} — {self.get_role_display()}"


class EventRegistration(models.Model):
    event = models.ForeignKey(
        ChurchEvent, on_delete=models.CASCADE, related_name="registrations"
    )
    member = models.ForeignKey(
        Member,
        verbose_name="pessoa cadastrada",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_registrations",
    )
    attendee_name = models.CharField("nome do visitante", max_length=180, blank=True)
    attendee_contact = models.CharField("contato", max_length=180, blank=True)
    attended = models.BooleanField("presente", default=False)
    registered_at = models.DateTimeField("inscrito em", auto_now_add=True)

    class Meta:
        ordering = ["attendee_name", "registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member"],
                condition=Q(member__isnull=False),
                name="unique_event_member_registration",
            ),
        ]
        verbose_name = "inscrição"
        verbose_name_plural = "inscrições"

    def __str__(self):
        return f"{self.display_name} — {self.event}"

    @property
    def display_name(self):
        return str(self.member) if self.member_id else self.attendee_name

    def clean(self):
        super().clean()
        if not self.member_id and not self.attendee_name.strip():
            raise ValidationError(
                {"attendee_name": "Informe o nome do visitante ou selecione uma pessoa cadastrada."}
            )


class ChurchSpace(models.Model):
    class Kind(models.TextChoices):
        TEMPLE = "temple", "Templo"
        HALL = "hall", "Salão"
        ROOM = "room", "Sala"
        EQUIPMENT = "equipment", "Equipamento"
        OTHER = "other", "Outro"

    name = models.CharField("nome do espaço/equipamento", max_length=120, unique=True)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices, default=Kind.ROOM)
    capacity = models.PositiveIntegerField("capacidade", null=True, blank=True)
    active = models.BooleanField("ativo para reservas", default=True)

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = "espaço ou equipamento"
        verbose_name_plural = "espaços e equipamentos"

    def __str__(self):
        return self.name


class SpaceReservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reservado"
        CANCELLED = "cancelled", "Cancelado"

    space = models.ForeignKey(
        ChurchSpace, verbose_name="espaço/equipamento", on_delete=models.PROTECT,
        related_name="reservations"
    )
    event = models.ForeignKey(
        ChurchEvent,
        verbose_name="evento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    purpose = models.CharField("finalidade", max_length=160)
    starts_at = models.DateTimeField("início")
    ends_at = models.DateTimeField("término")
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.RESERVED
    )
    notes = models.CharField("observações", max_length=240, blank=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        indexes = [models.Index(fields=["space", "starts_at", "ends_at"])]

    def __str__(self):
        return f"{self.space} — {self.purpose}"

    def clean(self):
        super().clean()
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "O término deve ser posterior ao início."
        if (
            self.status == self.Status.RESERVED
            and self.space_id
            and self.starts_at
            and self.ends_at
        ):
            overlaps = SpaceReservation.objects.filter(
                space_id=self.space_id,
                status=self.Status.RESERVED,
                starts_at__lt=self.ends_at,
                ends_at__gt=self.starts_at,
            )
            if self.pk:
                overlaps = overlaps.exclude(pk=self.pk)
            if overlaps.exists():
                errors["space"] = "Esse espaço ou equipamento já está reservado nesse período."
        if errors:
            raise ValidationError(errors)
