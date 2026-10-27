from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class ChurchAsset(models.Model):
    class Category(models.TextChoices):
        INSTRUMENT = "instrument", "Instrumento musical"
        FURNITURE = "furniture", "Móvel"
        COMPUTER = "computer", "Computador"
        EQUIPMENT = "equipment", "Equipamento"
        VEHICLE = "vehicle", "Veículo"
        PROPERTY = "property", "Imóvel"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        ACTIVE = "active", "Em uso"
        MAINTENANCE = "maintenance", "Em manutenção"
        DISPOSED = "disposed", "Baixado"

    name = models.CharField("nome do bem", max_length=160)
    category = models.CharField("categoria", max_length=20, choices=Category.choices)
    asset_tag = models.CharField(
        "número patrimonial", max_length=40, blank=True, unique=True
    )
    serial_number = models.CharField("número de série", max_length=100, blank=True)
    location = models.CharField("localização", max_length=160, blank=True)
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    acquired_on = models.DateField("data de aquisição", null=True, blank=True)
    purchase_value = models.DecimalField(
        "valor de aquisição",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "bem patrimonial"
        verbose_name_plural = "bens patrimoniais"

    def __str__(self):
        return self.name


class AssetMaintenance(models.Model):
    asset = models.ForeignKey(
        ChurchAsset,
        verbose_name="bem",
        on_delete=models.PROTECT,
        related_name="maintenance_records",
    )
    maintenance_date = models.DateField("data da manutenção")
    description = models.TextField("serviço realizado")
    cost = models.DecimalField(
        "custo",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    performed_by = models.CharField("responsável / fornecedor", max_length=160, blank=True)
    next_maintenance_on = models.DateField(
        "próxima manutenção", null=True, blank=True
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    class Meta:
        ordering = ["-maintenance_date", "-created_at"]
        verbose_name = "manutenção patrimonial"
        verbose_name_plural = "manutenções patrimoniais"

    def __str__(self):
        return f"{self.asset} — {self.maintenance_date:%d/%m/%Y}"

    def clean(self):
        super().clean()
        if (
            self.maintenance_date
            and self.next_maintenance_on
            and self.next_maintenance_on < self.maintenance_date
        ):
            raise ValidationError(
                {
                    "next_maintenance_on": (
                        "A próxima manutenção não pode ser anterior à data do serviço."
                    )
                }
            )


class Supplier(models.Model):
    name = models.CharField("nome / razão social", max_length=180)
    cnpj = models.CharField("CNPJ", max_length=14, blank=True)
    contact_name = models.CharField("pessoa de contato", max_length=160, blank=True)
    phone = models.CharField("telefone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    notes = models.TextField("observações", blank=True)
    active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.cnpj and (len(self.cnpj) != 14 or not self.cnpj.isdigit()):
            raise ValidationError({"cnpj": "Informe o CNPJ com 14 números."})


class Contract(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        CANCELLED = "cancelled", "Cancelado"

    title = models.CharField("título do contrato", max_length=180)
    contract_number = models.CharField("número do contrato", max_length=80, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="fornecedor",
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    start_date = models.DateField("início da vigência")
    end_date = models.DateField("fim da vigência")
    value = models.DecimalField(
        "valor total",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        "situação", max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["end_date", "title"]
        verbose_name = "contrato"
        verbose_name_plural = "contratos"
        indexes = [
            models.Index(fields=["status", "end_date"], name="contract_status_end_idx")
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "O fim da vigência não pode ser anterior ao início."}
            )

    def get_effective_status(self, today):
        if self.status == self.Status.CANCELLED:
            return "Cancelado"
        if self.end_date < today:
            return "Vencido"
        return "Ativo"


class AdministrativeTask(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        URGENT = "urgent", "Urgente"

    class Status(models.TextChoices):
        OPEN = "open", "Pendente"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluída"
        CANCELLED = "cancelled", "Cancelada"

    title = models.CharField("título", max_length=180)
    description = models.TextField("descrição", blank=True)
    due_date = models.DateField("prazo", null=True, blank=True)
    priority = models.CharField(
        "prioridade",
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        "situação", max_length=15, choices=Status.choices, default=Status.OPEN
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_administrative_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cadastrada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_administrative_tasks",
    )
    completed_at = models.DateTimeField("concluída em", null=True, blank=True)
    created_at = models.DateTimeField("cadastrada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["status", "due_date", "title"]
        verbose_name = "tarefa administrativa"
        verbose_name_plural = "tarefas administrativas"
        indexes = [
            models.Index(
                fields=["status", "due_date"], name="admin_task_status_due_idx"
            )
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)


class AdministrativeTaskAudit(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Criada"
        UPDATED = "updated", "Alterada"

    task = models.ForeignKey(
        AdministrativeTask,
        verbose_name="tarefa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    task_title = models.CharField("título da tarefa", max_length=180)
    action = models.CharField("ação", max_length=10, choices=Action.choices)
    before_data = models.JSONField("dados anteriores", null=True, blank=True)
    after_data = models.JSONField("dados posteriores")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="administrative_task_audit_entries",
    )
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "histórico de tarefa administrativa"
        verbose_name_plural = "históricos de tarefas administrativas"

    def __str__(self):
        return f"{self.task_title} — {self.get_action_display()}"
