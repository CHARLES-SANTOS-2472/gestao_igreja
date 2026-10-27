from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class FinancialCategory(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    name = models.CharField("nome", max_length=100)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField("cadastrada em", auto_now_add=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "name"], name="unique_financial_category_name"
            )
        ]
        verbose_name = "categoria financeira"
        verbose_name_plural = "categorias financeiras"

    def __str__(self):
        return self.name


class FinancialAccount(models.Model):
    class Kind(models.TextChoices):
        CASH = "cash", "Caixa"
        BANK = "bank", "Conta bancária"

    class AccountType(models.TextChoices):
        CHECKING = "checking", "Conta corrente"
        SAVINGS = "savings", "Poupança"
        PAYMENT = "payment", "Conta de pagamento"
        OTHER = "other", "Outra"

    class HolderType(models.TextChoices):
        INDIVIDUAL = "individual", "Pessoa física"
        COMPANY = "company", "Pessoa jurídica"

    name = models.CharField("nome", max_length=100, unique=True)
    kind = models.CharField(
        "tipo", max_length=10, choices=Kind.choices, default=Kind.CASH
    )
    bank_name = models.CharField("banco", max_length=100, blank=True)
    branch = models.CharField("agência", max_length=20, blank=True)
    account_number = models.CharField("número da conta", max_length=30, blank=True)
    account_type = models.CharField(
        "tipo da conta", max_length=12, choices=AccountType.choices, blank=True
    )
    holder_type = models.CharField(
        "titularidade",
        max_length=10,
        choices=HolderType.choices,
        blank=True,
    )
    holder_name = models.CharField("titular / razão social", max_length=160, blank=True)
    cnpj = models.CharField("CNPJ", max_length=14, blank=True)
    legal_representative_name = models.CharField(
        "nome do representante legal",
        max_length=160,
        blank=True,
    )
    legal_representative_cpf = models.CharField(
        "CPF do representante legal",
        max_length=11,
        blank=True,
    )
    opening_balance = models.DecimalField(
        "saldo inicial",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField("cadastrada em", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "conta financeira"
        verbose_name_plural = "contas financeiras"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        bank_fields = (
            "bank_name",
            "branch",
            "account_number",
            "account_type",
            "holder_type",
            "holder_name",
            "cnpj",
            "legal_representative_name",
            "legal_representative_cpf",
        )
        if self.kind == self.Kind.CASH:
            if any(getattr(self, field) for field in bank_fields):
                raise ValidationError(
                    {"kind": "Remova os dados bancários para cadastrar um caixa."}
                )
            return

        errors = {}
        for field in (
            "bank_name",
            "branch",
            "account_number",
            "account_type",
            "holder_type",
            "holder_name",
        ):
            if not getattr(self, field):
                errors[field] = "Este campo é obrigatório para conta bancária."
        if self.holder_type == self.HolderType.COMPANY:
            for field in (
                "cnpj",
                "legal_representative_name",
                "legal_representative_cpf",
            ):
                if not getattr(self, field):
                    errors[field] = "Obrigatório para conta de pessoa jurídica."
            if self.cnpj and (
                len(self.cnpj) != 14 or not self.cnpj.isdigit()
            ):
                errors["cnpj"] = "Informe o CNPJ com 14 números."
            if self.legal_representative_cpf and (
                len(self.legal_representative_cpf) != 11
                or not self.legal_representative_cpf.isdigit()
            ):
                errors["legal_representative_cpf"] = (
                    "Informe o CPF do representante com 11 números."
                )
        elif self.holder_type == self.HolderType.INDIVIDUAL:
            if self.cnpj or self.legal_representative_name or self.legal_representative_cpf:
                errors["holder_type"] = (
                    "Remova os dados de pessoa jurídica para titularidade de pessoa física."
                )
        elif self.cnpj or self.legal_representative_name or self.legal_representative_cpf:
            errors["holder_type"] = (
                "Informe a titularidade pessoa jurídica para os dados de CNPJ e representante."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def masked_account_number(self):
        if not self.account_number:
            return "—"
        return f"••••{self.account_number[-4:]}"


class FinancialTransaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Receita"
        EXPENSE = "expense", "Despesa"

    class PaymentMethod(models.TextChoices):
        PIX = "pix", "Pix"
        CREDIT_CARD = "credit_card", "Cartão de crédito"
        CASH = "cash", "Dinheiro"
        BANK_TRANSFER = "bank_transfer", "Transferência bancária"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SETTLED = "settled", "Quitada"
        CANCELLED = "cancelled", "Cancelada"

    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    title = models.CharField("descrição", max_length=160)
    category = models.ForeignKey(
        FinancialCategory,
        verbose_name="categoria",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    amount = models.DecimalField(
        "valor",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    due_on = models.DateField("data prevista")
    status = models.CharField(
        "situação",
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_method = models.CharField(
        "forma de recebimento/pagamento",
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
    )
    settled_on = models.DateField("data de recebimento/pagamento", null=True, blank=True)
    account = models.ForeignKey(
        FinancialAccount,
        verbose_name="conta",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    department = models.ForeignKey(
        "ministerios.Department",
        verbose_name="departamento / ministério",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    event = models.ForeignKey(
        "eventos.ChurchEvent",
        verbose_name="evento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    notes = models.TextField("observações", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="última alteração por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions_updated",
    )
    created_at = models.DateTimeField("registrada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["-due_on", "-created_at"]
        indexes = [
            models.Index(fields=["status", "due_on"], name="fin_tx_status_due_idx"),
            models.Index(fields=["kind", "settled_on"], name="fin_tx_kind_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="financial_transaction_amount_positive",
            )
        ]
        verbose_name = "lançamento financeiro"
        verbose_name_plural = "lançamentos financeiros"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.category_id and self.kind != self.category.kind:
            raise ValidationError(
                {"category": "A categoria precisa corresponder ao tipo do lançamento."}
            )
        if self.status == self.Status.SETTLED:
            errors = {}
            if not self.account_id:
                errors["account"] = "Informe a conta para lançamentos recebidos/pagos."
            if not self.settled_on:
                errors["settled_on"] = (
                    "Informe a data do recebimento ou pagamento."
                )
            if errors:
                raise ValidationError(errors)
        elif self.status == self.Status.PENDING and (
            self.account_id or self.settled_on
        ):
            raise ValidationError(
                "Lançamentos pendentes não devem ter conta ou data de quitação."
            )
        elif self.status == self.Status.CANCELLED and (
            self.account_id or self.settled_on
        ):
            raise ValidationError(
                "Remova a conta e a data de quitação antes de cancelar o lançamento."
            )

    @property
    def settled_status_label(self):
        if self.kind == self.Kind.EXPENSE:
            return "Paga"
        return "Recebida"


class FinancialTransactionAudit(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Criado"
        UPDATED = "updated", "Alterado"

    transaction = models.ForeignKey(
        FinancialTransaction,
        verbose_name="lançamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    transaction_label = models.CharField("descrição do lançamento", max_length=160)
    action = models.CharField("ação", max_length=10, choices=Action.choices)
    before_data = models.JSONField("dados anteriores", null=True, blank=True)
    after_data = models.JSONField("dados posteriores")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_audit_entries",
    )
    created_at = models.DateTimeField("data da alteração", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "histórico financeiro"
        verbose_name_plural = "históricos financeiros"

    def __str__(self):
        return f"{self.get_action_display()} — {self.transaction_label}"


class DonationRecord(models.Model):
    class DonationType(models.TextChoices):
        MONEY = "money", "Dinheiro"
        GOODS = "goods", "Bens"

    class Destination(models.TextChoices):
        GENERAL = "general", "Uso geral da igreja"
        SOCIAL_ASSISTANCE = "social", "Assistência Social"
        DEPARTMENT = "department", "Departamento / ministério"
        EVENT = "event", "Evento"
        OTHER = "other", "Outra finalidade"

    class Status(models.TextChoices):
        RECEIVED = "received", "Recebida"
        CANCELLED = "cancelled", "Cancelada"

    donor_name = models.CharField("nome do doador", max_length=160, blank=True)
    anonymous = models.BooleanField("doação anônima", default=False)
    received_on = models.DateField("data do recebimento")
    donation_type = models.CharField(
        "tipo de doação", max_length=10, choices=DonationType.choices
    )
    description = models.CharField("descrição do item", max_length=180, blank=True)
    amount = models.DecimalField(
        "valor recebido",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    quantity = models.DecimalField(
        "quantidade recebida",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
    )
    unit = models.CharField("unidade", max_length=30, blank=True)
    destination = models.CharField(
        "destinação", max_length=20, choices=Destination.choices
    )
    department = models.ForeignKey(
        "ministerios.Department",
        verbose_name="departamento / ministério",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="donation_records",
    )
    event = models.ForeignKey(
        "eventos.ChurchEvent",
        verbose_name="evento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="donation_records",
    )
    destination_description = models.CharField(
        "descrição da finalidade", max_length=180, blank=True
    )
    financial_transaction = models.OneToOneField(
        FinancialTransaction,
        verbose_name="receita financeira vinculada",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="donation_record",
    )
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.RECEIVED
    )
    cancellation_reason = models.CharField(
        "motivo do cancelamento", max_length=240, blank=True
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="donations_recorded",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cancelada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="donations_cancelled",
    )
    cancelled_at = models.DateTimeField("cancelada em", null=True, blank=True)
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    class Meta:
        ordering = ["-received_on", "-created_at"]
        verbose_name = "doação recebida"
        verbose_name_plural = "doações recebidas"

    def __str__(self):
        return f"{self.get_donation_type_display()} — {self.get_destination_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.anonymous and self.donor_name:
            errors["donor_name"] = "Remova o nome para registrar uma doação anônima."
        if self.donation_type == self.DonationType.MONEY:
            if self.amount is None:
                errors["amount"] = "Informe o valor da doação."
            if self.quantity is not None or self.unit:
                errors["quantity"] = "Quantidade e unidade são exclusivas de bens."
            if self.financial_transaction_id and (
                self.financial_transaction.kind != FinancialTransaction.Kind.INCOME
                or self.financial_transaction.amount != self.amount
            ):
                errors["financial_transaction"] = (
                    "A receita vinculada deve corresponder ao valor recebido."
                )
        elif self.donation_type == self.DonationType.GOODS:
            if not self.description:
                errors["description"] = "Descreva o bem recebido."
            if self.quantity is None:
                errors["quantity"] = "Informe a quantidade recebida."
            if not self.unit:
                errors["unit"] = "Informe a unidade da quantidade."
            if self.amount is not None:
                errors["amount"] = "Bens doados não recebem valor financeiro neste cadastro."
            if self.financial_transaction_id:
                errors["financial_transaction"] = (
                    "Doações de bens não devem ter receita financeira vinculada."
                )
        if (
            self.destination == self.Destination.DEPARTMENT
            and not self.department_id
        ):
            errors["department"] = "Selecione o departamento de destino."
        if self.destination == self.Destination.EVENT and not self.event_id:
            errors["event"] = "Selecione o evento de destino."
        if (
            self.destination == self.Destination.OTHER
            and not self.destination_description
        ):
            errors["destination_description"] = (
                "Descreva a finalidade da doação."
            )
        if self.destination == self.Destination.DEPARTMENT and self.event_id:
            errors["event"] = "Remova o evento para destinar ao departamento."
        if self.destination == self.Destination.EVENT and self.department_id:
            errors["department"] = "Remova o departamento para destinar ao evento."
        if self.destination in (
            self.Destination.GENERAL,
            self.Destination.SOCIAL_ASSISTANCE,
            self.Destination.OTHER,
        ) and (self.department_id or self.event_id):
            errors["destination"] = (
                "Remova o departamento e o evento para esta destinação."
            )
        if self.status == self.Status.CANCELLED and not self.cancellation_reason:
            errors["cancellation_reason"] = "Informe o motivo do cancelamento."
        if errors:
            raise ValidationError(errors)
