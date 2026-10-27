from django import forms
import re

from .models import (
    AdministrativeTask,
    AssetMaintenance,
    ChurchAsset,
    Contract,
    Supplier,
)


class ChurchAssetForm(forms.ModelForm):
    class Meta:
        model = ChurchAsset
        fields = (
            "name",
            "category",
            "asset_tag",
            "serial_number",
            "location",
            "status",
            "acquired_on",
            "purchase_value",
            "description",
        )
        widgets = {
            "acquired_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "purchase_value": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class AssetMaintenanceForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenance
        fields = (
            "maintenance_date",
            "description",
            "cost",
            "performed_by",
            "next_maintenance_on",
        )
        widgets = {
            "maintenance_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "next_maintenance_on": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class SupplierForm(forms.ModelForm):
    cnpj = forms.CharField(
        label="CNPJ",
        required=False,
        max_length=18,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "inputmode": "numeric", "maxlength": 18}
        ),
    )

    class Meta:
        model = Supplier
        fields = ("name", "cnpj", "contact_name", "phone", "email", "notes", "active")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def clean_cnpj(self):
        value = re.sub(r"\D", "", self.cleaned_data.get("cnpj", ""))
        if value and len(value) != 14:
            raise forms.ValidationError("Informe o CNPJ com 14 números.")
        return value


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = (
            "title",
            "contract_number",
            "supplier",
            "start_date",
            "end_date",
            "value",
            "status",
            "notes",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "value": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        suppliers = Supplier.objects.filter(active=True)
        if self.instance.pk and self.instance.supplier_id:
            suppliers = suppliers | Supplier.objects.filter(
                pk=self.instance.supplier_id
            )
        self.fields["supplier"].queryset = suppliers.distinct()


class AdministrativeTaskForm(forms.ModelForm):
    class Meta:
        model = AdministrativeTask
        fields = (
            "title",
            "description",
            "due_date",
            "priority",
            "status",
            "assigned_to",
        )
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = self.fields[
            "assigned_to"
        ].queryset.filter(is_active=True).order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = "Sem responsável"
        self.fields["description"].help_text = (
            "Não registre aqui informações pastorais, dados sensíveis ou credenciais."
        )
