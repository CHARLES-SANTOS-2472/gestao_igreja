import re

from django import forms
from django.db.models import Q
from django.utils import timezone

from eventos.models import ChurchEvent
from ministerios.models import Department

from .models import (
    DonationRecord,
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
)


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = (
            "kind",
            "title",
            "category",
            "amount",
            "due_on",
            "status",
            "payment_method",
            "settled_on",
            "account",
            "department",
            "event",
            "notes",
        )
        widgets = {
            "due_on": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "settled_on": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial.setdefault("due_on", timezone.localdate())
        self.fields["payment_method"].required = False
        self.fields["payment_method"].help_text = (
            "Informe a forma usada quando o recebimento ou pagamento já tiver "
            "sido conferido."
        )
        kind = (
            self.data.get("kind")
            if self.is_bound
            else self.instance.kind
        )
        category_filter = Q(active=True)
        if kind in FinancialCategory.Kind.values:
            category_filter &= Q(kind=kind)
        elif self.instance.pk:
            category_filter &= Q(kind=self.instance.kind)
        self.fields["category"].queryset = FinancialCategory.objects.filter(
            category_filter
        )
        if self.instance.pk and self.instance.category_id:
            self.fields["category"].queryset = (
                self.fields["category"].queryset
                | FinancialCategory.objects.filter(pk=self.instance.category_id)
            ).distinct()
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        if self.instance.pk and self.instance.account_id:
            self.fields["account"].queryset = (
                self.fields["account"].queryset
                | FinancialAccount.objects.filter(pk=self.instance.account_id)
            ).distinct()
        self.fields["account"].required = False
        self.fields["account"].empty_label = "Selecione quando estiver quitado"
        self.fields["settled_on"].required = False
        self.fields["department"].queryset = Department.objects.filter(active=True)
        self.fields["department"].required = False
        self.fields["department"].empty_label = "Nenhum departamento"
        event_filter = ~Q(status=ChurchEvent.Status.CANCELLED)
        if self.instance.pk and self.instance.event_id:
            event_filter |= Q(pk=self.instance.event_id)
        self.fields["event"].queryset = ChurchEvent.objects.filter(event_filter)
        self.fields["event"].required = False
        self.fields["event"].empty_label = "Nenhum evento"

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get("kind")
        category = cleaned_data.get("category")
        if category and kind and category.kind != kind:
            self.add_error(
                "category", "Selecione uma categoria compatível com o tipo."
            )
        if (
            not self.instance.pk
            and kind == FinancialTransaction.Kind.INCOME
            and category
            and category.name == "Doações"
        ):
            self.add_error(
                "category",
                "Registre doações pela área de Doações para manter o vínculo "
                "com o recebimento e evitar duplicidade.",
            )
        status = cleaned_data.get("status")
        account = cleaned_data.get("account")
        settled_on = cleaned_data.get("settled_on")
        if status == FinancialTransaction.Status.SETTLED:
            if not account:
                self.add_error("account", "Selecione a conta usada.")
            if not settled_on:
                self.add_error("settled_on", "Informe a data da quitação.")
        elif status == FinancialTransaction.Status.PENDING:
            if account:
                self.add_error(
                    "account", "Lançamentos pendentes ainda não movimentam uma conta."
                )
            if settled_on:
                self.add_error(
                    "settled_on", "Lançamentos pendentes não têm data de quitação."
                )
        if status == FinancialTransaction.Status.CANCELLED and (
            account or settled_on
        ):
            self.add_error(
                None,
                "Remova a conta e a data de quitação antes de cancelar o lançamento.",
            )
        return cleaned_data


class FinancialCategoryForm(forms.ModelForm):
    class Meta:
        model = FinancialCategory
        fields = ("name", "kind", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.transactions.exists():
            self.fields["kind"].disabled = True
            self.fields["kind"].help_text = (
                "O tipo não pode ser alterado enquanto houver lançamentos associados."
            )


class FinancialAccountForm(forms.ModelForm):
    cnpj = forms.CharField(
        label="CNPJ",
        required=False,
        max_length=18,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "inputmode": "numeric", "maxlength": 18}
        ),
    )
    legal_representative_cpf = forms.CharField(
        label="CPF do representante legal",
        required=False,
        max_length=14,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "inputmode": "numeric", "maxlength": 14}
        ),
    )

    class Meta:
        model = FinancialAccount
        fields = (
            "name",
            "kind",
            "bank_name",
            "branch",
            "account_number",
            "account_type",
            "holder_type",
            "holder_name",
            "cnpj",
            "legal_representative_name",
            "legal_representative_cpf",
            "opening_balance",
            "active",
        )
        widgets = {
            "opening_balance": forms.NumberInput(
                attrs={"step": "0.01", "min": "0"}
            ),
            "account_number": forms.TextInput(
                attrs={"autocomplete": "off", "inputmode": "numeric"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.transactions.exists():
            for field_name in ("kind", "opening_balance"):
                self.fields[field_name].disabled = True
            self.fields["opening_balance"].help_text = (
                "O saldo inicial não pode ser alterado após movimentações; "
                "registre os ajustes como lançamentos financeiros."
            )
        for field_name in (
            "bank_name",
            "branch",
            "account_number",
            "account_type",
            "holder_type",
            "holder_name",
        ):
            self.fields[field_name].required = False
        self.fields["holder_type"].choices = (
            ("", "Selecione a titularidade"),
            *FinancialAccount.HolderType.choices,
        )
        self.fields["account_type"].choices = (
            ("", "Selecione o tipo de conta"),
            *FinancialAccount.AccountType.choices,
        )

    def clean_cnpj(self):
        value = re.sub(r"\D", "", self.cleaned_data.get("cnpj", ""))
        if value and len(value) != 14:
            raise forms.ValidationError("Informe o CNPJ com 14 números.")
        return value

    def clean_legal_representative_cpf(self):
        value = re.sub(
            r"\D", "", self.cleaned_data.get("legal_representative_cpf", "")
        )
        if value and len(value) != 11:
            raise forms.ValidationError(
                "Informe o CPF do representante com 11 números."
            )
        return value


class FinancialTransactionFilterForm(forms.Form):
    q = forms.CharField(label="Buscar", required=False)
    kind = forms.ChoiceField(
        label="Tipo",
        choices=(("", "Todos"), *FinancialTransaction.Kind.choices),
        required=False,
    )
    status = forms.ChoiceField(
        label="Situação",
        choices=(("", "Todas"), *FinancialTransaction.Status.choices),
        required=False,
    )
    category = forms.ModelChoiceField(
        label="Categoria",
        queryset=FinancialCategory.objects.none(),
        required=False,
        empty_label="Todas as categorias",
    )
    date_from = forms.DateField(
        label="De",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        label="Até",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = FinancialCategory.objects.filter(active=True)

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error(
                "date_to", "A data final deve ser igual ou posterior à inicial."
            )
        return cleaned_data


class FinancialReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="Data inicial",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        label="Data final",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error(
                "date_to", "A data final deve ser igual ou posterior à inicial."
            )
        return cleaned_data


class DonationRecordForm(forms.ModelForm):
    account = forms.ModelChoiceField(
        label="Conta que recebeu",
        queryset=FinancialAccount.objects.none(),
        required=False,
    )
    payment_method = forms.ChoiceField(
        label="Forma de recebimento",
        choices=(("", "Selecione"), *FinancialTransaction.PaymentMethod.choices),
        required=False,
    )

    class Meta:
        model = DonationRecord
        fields = (
            "donor_name",
            "anonymous",
            "received_on",
            "donation_type",
            "description",
            "amount",
            "quantity",
            "unit",
            "destination",
            "department",
            "event",
            "destination_description",
        )
        widgets = {
            "received_on": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "quantity": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, can_view_accounts=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("received_on", timezone.localdate())
        if can_view_accounts:
            self.fields["account"].queryset = FinancialAccount.objects.filter(
                active=True
            )
        self.fields["department"].queryset = Department.objects.filter(active=True)
        self.fields["department"].required = False
        self.fields["department"].empty_label = "Selecione o ministério"
        event_queryset = ChurchEvent.objects.exclude(
            status=ChurchEvent.Status.CANCELLED
        )
        self.fields["event"].queryset = event_queryset
        self.fields["event"].required = False
        self.fields["event"].empty_label = "Selecione o evento"
        self.fields["description"].required = False

    def clean(self):
        cleaned_data = super().clean()
        donation_type = cleaned_data.get("donation_type")
        if cleaned_data.get("anonymous"):
            cleaned_data["donor_name"] = ""
            self.instance.donor_name = ""
        if donation_type == DonationRecord.DonationType.MONEY:
            if not cleaned_data.get("amount"):
                self.add_error("amount", "Informe o valor recebido.")
            if not cleaned_data.get("account"):
                self.add_error("account", "Selecione a conta que recebeu o valor.")
        elif donation_type == DonationRecord.DonationType.GOODS:
            if not cleaned_data.get("description"):
                self.add_error("description", "Descreva o bem recebido.")
        destination = cleaned_data.get("destination")
        if destination == DonationRecord.Destination.DEPARTMENT and not cleaned_data.get(
            "department"
        ):
            self.add_error("department", "Selecione o departamento de destino.")
        if destination == DonationRecord.Destination.EVENT and not cleaned_data.get(
            "event"
        ):
            self.add_error("event", "Selecione o evento de destino.")
        if destination == DonationRecord.Destination.OTHER and not cleaned_data.get(
            "destination_description"
        ):
            self.add_error(
                "destination_description", "Descreva a finalidade da doação."
            )
        return cleaned_data


class DonationCancellationForm(forms.Form):
    reason = forms.CharField(
        label="Motivo do cancelamento",
        max_length=240,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
