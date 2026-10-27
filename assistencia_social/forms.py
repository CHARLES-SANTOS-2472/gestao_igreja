from django import forms

from .models import AssistanceRecord, AssistedFamily


class AssistedFamilyForm(forms.ModelForm):
    class Meta:
        model = AssistedFamily
        fields = (
            "reference_name",
            "contact_name",
            "phone",
            "postal_code",
            "street",
            "number",
            "address_extra",
            "neighborhood",
            "city",
            "state",
            "household_size",
            "active",
        )
        widgets = {
            "household_size": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "postal_code": forms.TextInput(
                attrs={
                    "autocomplete": "postal-code",
                    "inputmode": "numeric",
                    "maxlength": "9",
                }
            ),
            "street": forms.TextInput(attrs={"autocomplete": "address-line1"}),
            "number": forms.TextInput(attrs={"autocomplete": "address-line2"}),
            "address_extra": forms.TextInput(),
            "neighborhood": forms.TextInput(),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "state": forms.TextInput(
                attrs={"autocomplete": "address-level1", "maxlength": "2"}
            ),
        }


class AssistanceRecordForm(forms.ModelForm):
    class Meta:
        model = AssistanceRecord
        fields = (
            "aid_type",
            "description",
            "quantity",
            "amount",
            "assistance_date",
            "status",
        )
        widgets = {
            "assistance_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "quantity": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.family = family
        self.fields["description"].help_text = (
            "Informe somente os itens ou a finalidade operacional. "
            "Não registre diagnósticos, relatos pastorais ou documentos pessoais."
        )
        self.fields["amount"].required = False
        self.fields["amount"].help_text = (
            "Preencha apenas quando o tipo de ajuda for financeira."
        )

    def clean(self):
        cleaned_data = super().clean()
        aid_type = cleaned_data.get("aid_type")
        amount = cleaned_data.get("amount")
        if aid_type == AssistanceRecord.AidType.FINANCIAL and amount is None:
            self.add_error("amount", "Informe o valor da ajuda financeira.")
        elif aid_type and aid_type != AssistanceRecord.AidType.FINANCIAL and amount:
            self.add_error("amount", "Informe valor somente para ajuda financeira.")
        return cleaned_data


class AssistanceRecordFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=(("", "Todas"), *AssistanceRecord.Status.choices),
    )
    aid_type = forms.ChoiceField(
        label="Tipo de ajuda",
        required=False,
        choices=(("", "Todos"), *AssistanceRecord.AidType.choices),
    )
    date_from = forms.DateField(
        label="De",
        required=False,
        input_formats=("%Y-%m-%d",),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Até",
        required=False,
        input_formats=("%Y-%m-%d",),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_to < date_from:
            self.add_error("date_to", "A data final deve ser igual ou posterior à inicial.")
        return cleaned_data
