from django.core.exceptions import ValidationError
from django.db import models

from membros.models import Member


class Department(models.Model):
    name = models.CharField("nome", max_length=120, unique=True)
    description = models.TextField("descrição", blank=True)
    leader = models.ForeignKey(
        Member,
        verbose_name="líder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_departments",
    )
    vice_leader = models.ForeignKey(
        Member,
        verbose_name="vice-líder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vice_led_departments",
    )
    members = models.ManyToManyField(
        Member,
        verbose_name="membros e congregados",
        blank=True,
        through="DepartmentMembership",
        related_name="departments",
    )
    active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "departamento ou ministério"
        verbose_name_plural = "departamentos e ministérios"

    def __str__(self):
        return self.name


class DepartmentMembership(models.Model):
    class Role(models.TextChoices):
        LEADER = "leader", "Líder"
        VICE_LEADER = "vice_leader", "Vice-líder"
        PARTICIPANT = "participant", "Participante"

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="department_memberships",
    )
    role = models.CharField(
        "função no ministério",
        max_length=20,
        choices=Role.choices,
        default=Role.PARTICIPANT,
    )

    class Meta:
        ordering = ["role", "member__first_name", "member__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "member"],
                name="unique_department_membership",
            ),
            models.UniqueConstraint(
                fields=["department"],
                condition=models.Q(role="leader"),
                name="unique_department_leader",
            ),
            models.UniqueConstraint(
                fields=["department"],
                condition=models.Q(role="vice_leader"),
                name="unique_department_vice_leader",
            ),
        ]
        verbose_name = "vínculo com departamento"
        verbose_name_plural = "vínculos com departamentos"

    def __str__(self):
        return f"{self.member} — {self.get_role_display()}"


class DepartmentActivity(models.Model):
    class Kind(models.TextChoices):
        MEETING = "meeting", "Reunião"
        ACTIVITY = "activity", "Atividade"
        REHEARSAL = "rehearsal", "Ensaio"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planejada"
        COMPLETED = "completed", "Realizada"
        CANCELLED = "cancelled", "Cancelada"

    department = models.ForeignKey(
        Department,
        verbose_name="departamento",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    title = models.CharField("título", max_length=160)
    kind = models.CharField(
        "tipo", max_length=20, choices=Kind.choices, default=Kind.MEETING
    )
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    starts_at = models.DateTimeField("início")
    ends_at = models.DateTimeField("término", null=True, blank=True)
    location = models.CharField("local", max_length=180, blank=True)
    description = models.TextField("observações", blank=True)
    responsible = models.ForeignKey(
        Member,
        verbose_name="responsável",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_activities",
    )
    participants = models.ManyToManyField(
        Member,
        verbose_name="participantes",
        blank=True,
        related_name="department_activity_participations",
    )
    created_at = models.DateTimeField("cadastrada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["starts_at", "title"]
        verbose_name = "reunião ou atividade"
        verbose_name_plural = "reuniões e atividades"
        indexes = [
            models.Index(
                fields=["department", "starts_at"],
                name="min_act_dept_start_idx",
            )
        ]
        permissions = [
            ("view_departmentattendance", "Pode visualizar relatórios de presença"),
            ("manage_departmentattendance", "Pode registrar presença em atividades"),
            ("manage_departmentactivityscales", "Pode gerenciar escalas de atividades"),
        ]

    def __str__(self):
        return self.title


class DepartmentActivityAttendance(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Não registrado"
        PRESENT = "present", "Presente"
        ABSENT = "absent", "Ausente"

    activity = models.ForeignKey(
        DepartmentActivity,
        verbose_name="atividade",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    member = models.ForeignKey(
        Member,
        verbose_name="participante",
        on_delete=models.CASCADE,
        related_name="department_activity_attendance",
    )
    status = models.CharField(
        "presença",
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["member__first_name", "member__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "member"],
                name="unique_department_activity_attendance",
            )
        ]
        verbose_name = "presença em atividade"
        verbose_name_plural = "presenças em atividades"

    def __str__(self):
        return f"{self.member} — {self.get_status_display()}"


class DepartmentActivityAssignment(models.Model):
    class Role(models.TextChoices):
        PREACHER = "preacher", "Pregador(a)"
        SERVICE_LEADER = "service_leader", "Dirigente"
        MUSICIAN = "musician", "Músico(a)"
        RECEPTION = "reception", "Recepção"
        SUPPORT = "support", "Apoio / equipe"
        INTERCESSION = "intercession", "Intercessão"
        OTHER = "other", "Outra função"

    activity = models.ForeignKey(
        DepartmentActivity,
        verbose_name="atividade",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    member = models.ForeignKey(
        Member,
        verbose_name="pessoa escalada",
        on_delete=models.CASCADE,
        related_name="department_activity_assignments",
    )
    role = models.CharField(
        "função",
        max_length=24,
        choices=Role.choices,
    )
    custom_role = models.CharField(
        "descrição da outra função",
        max_length=100,
        blank=True,
    )

    class Meta:
        ordering = ["role", "member__first_name", "member__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "member", "role", "custom_role"],
                name="unique_department_activity_assignment",
            )
        ]
        verbose_name = "escala de atividade"
        verbose_name_plural = "escalas de atividades"

    def clean(self):
        if (
            self.activity_id
            and self.member_id
            and not self.activity.department.members.filter(pk=self.member_id).exists()
        ):
            raise ValidationError(
                {"member": "A pessoa precisa estar vinculada ao ministério da atividade."}
            )
        if self.role == self.Role.OTHER and not self.custom_role.strip():
            raise ValidationError(
                {"custom_role": "Descreva a função quando selecionar Outra função."}
            )
        if self.role != self.Role.OTHER and self.custom_role:
            raise ValidationError(
                {"custom_role": "Preencha este campo somente para Outra função."}
            )

    @property
    def role_label(self):
        if self.role == self.Role.OTHER:
            return self.custom_role
        return self.get_role_display()

    def __str__(self):
        return f"{self.member} — {self.role_label}"
