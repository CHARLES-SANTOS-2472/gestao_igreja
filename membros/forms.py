from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CboOccupation, Member


class FamilyMemberMultipleChoiceField(forms.ModelMultipleChoiceField):
    def clean(self, value):
        if value is None:
            value = []
        elif not isinstance(value, (list, tuple)):
            value = [value]
        value = [item for item in value if item not in self.empty_values]
        return super().clean(value)


class MemberForm(forms.ModelForm):
    occupation_search = forms.CharField(
        label="Profissão pela Classificação Brasileira de Ocupações (CBO)",
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "placeholder": "Digite o nome ou código da profissão",
                "aria-describedby": "occupation-help occupation-status",
            }
        ),
    )
    occupation_code = forms.CharField(required=False, widget=forms.HiddenInput())
    spouse_name = forms.CharField(
        label="Nome do cônjuge",
        max_length=251,
        required=False,
        help_text="Opcional. Se ainda não tiver cadastro, será criado um vínculo provisório.",
    )
    parents = FamilyMemberMultipleChoiceField(
        label="Selecionar pais/responsáveis já cadastrados",
        queryset=Member.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 1, "class": "family-select"}),
        help_text="Opcional. Selecione uma pessoa por campo; use “Adicionar outro” para incluir mais.",
    )
    parents_names = forms.CharField(
        label="Nome dos pais/responsáveis",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Um nome completo por linha"}),
        help_text="Opcional. Um nome por linha; cada pessoa receberá um cadastro provisório.",
    )
    children = FamilyMemberMultipleChoiceField(
        label="Selecionar filhos já cadastrados",
        queryset=Member.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 1, "class": "family-select"}),
        help_text="Opcional. Selecione uma pessoa por campo; use “Adicionar outro” para incluir mais.",
    )
    children_names = forms.CharField(
        label="Nome dos filhos",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Um nome completo por linha"}),
        help_text="Opcional. Um nome por linha; cada pessoa receberá um cadastro provisório.",
    )

    class Meta:
        model = Member
        fields = (
            "first_name",
            "last_name",
            "cpf",
            "rg",
            "birth_date",
            "is_deceased",
            "deceased_on",
            "profession",
            "landline",
            "mobile",
            "email",
            "postal_code",
            "street",
            "number",
            "address_extra",
            "neighborhood",
            "city",
            "state",
            "status",
            "joined_on",
            "baptized_on",
            "baptized_at",
            "spouse",
            "parents",
            "is_placeholder",
            "email_consent",
            "whatsapp_consent",
        )
        widgets = {
            "birth_date": forms.DateInput(
                attrs={
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "inputmode": "numeric",
                    "pattern": "[0-9]{2}/[0-9]{2}/[0-9]{4}",
                },
                format="%d/%m/%Y",
            ),
            "joined_on": forms.DateInput(
                attrs={
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "inputmode": "numeric",
                    "pattern": "[0-9]{2}/[0-9]{2}/[0-9]{4}",
                },
                format="%d/%m/%Y",
            ),
            "baptized_on": forms.DateInput(
                attrs={
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "inputmode": "numeric",
                    "pattern": "[0-9]{2}/[0-9]{2}/[0-9]{4}",
                },
                format="%d/%m/%Y",
            ),
            "deceased_on": forms.DateInput(
                attrs={
                    "type": "text",
                    "placeholder": "dd/mm/aaaa",
                    "inputmode": "numeric",
                    "pattern": "[0-9]{2}/[0-9]{2}/[0-9]{4}",
                },
                format="%d/%m/%Y",
            ),
            "spouse": forms.Select(),
            "is_deceased": forms.CheckboxInput(),
            "is_placeholder": forms.CheckboxInput(),
            "email_consent": forms.CheckboxInput(),
            "whatsapp_consent": forms.CheckboxInput(),
        }
        labels = {"is_deceased": "Falecido(a) (in memoriam)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profession"].label = "Outra profissão (se não encontrar na CBO)"
        self.fields["profession"].help_text = (
            "Use este campo apenas para ocupações não encontradas no catálogo oficial."
        )
        if self.instance.pk:
            occupation = self.instance.cbo_occupation
            if occupation:
                self.initial["occupation_search"] = str(occupation)
                self.initial["occupation_code"] = occupation.code
        self._original_values = {}
        if self.instance.pk:
            self._original_values = {
                field_name: getattr(self.instance, field_name)
                for field_name in (
                    "birth_date",
                    "joined_on",
                    "baptized_on",
                    "deceased_on",
                    "spouse_id",
                    "cbo_occupation_id",
                )
            }
        available = Member.objects.order_by("first_name", "last_name")
        if self.instance.pk:
            available = available.exclude(pk=self.instance.pk)
        self.fields["spouse"].queryset = available
        self.fields["spouse"].required = False
        self.fields["spouse"].empty_label = "Nenhum"
        self.fields["spouse"].label = "Selecionar cônjuge já cadastrado"
        self.fields["spouse"].help_text = "Opcional. Use se a pessoa já tiver cadastro."
        if self.instance.pk:
            self.initial["spouse"] = (
                self.instance.spouse or self.instance.spouse_links.first()
            )
        self.fields["parents"].queryset = available
        self.fields["children"].queryset = available
        for field_name in ("birth_date", "joined_on", "baptized_on", "deceased_on"):
            self.fields[field_name].input_formats = ["%d/%m/%Y"]
        if self.instance.pk:
            self.initial["parents"] = self.instance.parents.all()
            self.initial["children"] = self.instance.children.all()

    @staticmethod
    def _parse_names(value):
        names = []
        seen = set()
        for line in value.splitlines():
            name = " ".join(line.split())
            if not name:
                continue
            MemberForm._validate_name(name)
            normalized = name.casefold()
            if normalized not in seen:
                names.append(name)
                seen.add(normalized)
        return names

    @staticmethod
    def _validate_name(name):
        first_name, _, last_name = name.partition(" ")
        if len(first_name) > 100 or len(last_name) > 150:
            raise ValidationError(
                "O primeiro nome pode ter até 100 caracteres e o sobrenome, até 150."
            )

    def clean_spouse_name(self):
        name = " ".join(self.cleaned_data["spouse_name"].split())
        if name:
            self._validate_name(name)
        return name

    def clean_parents_names(self):
        return self._parse_names(self.cleaned_data["parents_names"])

    def clean_children_names(self):
        return self._parse_names(self.cleaned_data["children_names"])

    def clean_cpf(self):
        cpf = self.cleaned_data["cpf"]
        return cpf.strip() or ""

    def clean(self):
        cleaned_data = super().clean()
        occupation_code = cleaned_data.get("occupation_code", "").strip()
        occupation_search = cleaned_data.get("occupation_search", "").strip()
        selected_occupation = None
        if occupation_code:
            try:
                selected_occupation = CboOccupation.objects.get(pk=occupation_code)
            except CboOccupation.DoesNotExist:
                self.add_error(
                    "occupation_search",
                    "A profissão selecionada não está disponível no catálogo CBO.",
                )
            else:
                cleaned_data["_selected_occupation"] = selected_occupation
                if occupation_search and occupation_search != str(selected_occupation):
                    self.add_error(
                        "occupation_search",
                        "Selecione uma profissão da lista de sugestões.",
                    )
                if cleaned_data.get("profession", "").strip():
                    self.add_error(
                        "profession",
                        "Preencha a profissão CBO ou a outra profissão, não ambas.",
                    )
        elif occupation_search:
            self.add_error(
                "occupation_search",
                "Escolha uma profissão na lista de sugestões ou use o campo de outra profissão.",
            )

        spouse = cleaned_data.get("spouse")
        spouse_name = cleaned_data.get("spouse_name", "").strip()
        parents = cleaned_data.get("parents")
        children = cleaned_data.get("children")
        if spouse and spouse_name:
            self.add_error(
                "spouse_name",
                "Use a seleção de cônjuge ou informe um nome novo, não os dois.",
            )
        if self.instance.pk and spouse and spouse.pk == self.instance.pk:
            self.add_error("spouse", "A pessoa não pode ser vinculada como seu próprio cônjuge.")
        if spouse and (
            spouse.spouse_id not in (None, self.instance.pk)
            or spouse.spouse_links.exclude(pk=self.instance.pk).exists()
        ):
            self.add_error("spouse", "Esse cadastro já está vinculado a outro cônjuge.")
        if parents is not None and children is not None:
            if set(parents.values_list("pk", flat=True)) & set(
                children.values_list("pk", flat=True)
            ):
                raise ValidationError(
                    "A mesma pessoa não pode ser vinculada simultaneamente como pai/responsável e filho."
                )
        if cleaned_data.get("is_placeholder"):
            if cleaned_data.get("status") != Member.Status.PENDING:
                self.add_error(
                    "status",
                    "Um cadastro incompleto deve usar a situação 'Cadastro familiar incompleto'.",
                )
        elif cleaned_data.get("status") == Member.Status.PENDING:
            self.add_error(
                "status",
                "Selecione a situação da pessoa ou marque o cadastro como incompleto.",
            )
        if cleaned_data.get("deceased_on") and not cleaned_data.get("is_deceased"):
            self.add_error(
                "deceased_on",
                "Marque a opção “Falecido(a) (in memoriam)” para informar a data.",
            )
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        member = super().save(commit=False)
        if commit:
            if "occupation_code" in self.data:
                member.cbo_occupation = self.cleaned_data.get("_selected_occupation")
            elif self.instance.pk:
                member.cbo_occupation_id = self._original_values["cbo_occupation_id"]
            for field_name in ("birth_date", "joined_on", "baptized_on", "deceased_on"):
                if field_name not in self.data and field_name in self._original_values:
                    setattr(member, field_name, self._original_values[field_name])
            if "spouse" not in self.data and self.instance.pk:
                member.spouse_id = self._original_values["spouse_id"]
            spouse = member.spouse
            if "spouse" in self.data:
                Member.objects.filter(spouse_id=member.pk).exclude(
                    pk=spouse.pk if spouse else None
                ).update(spouse=None)
                if spouse and spouse.spouse_id == member.pk:
                    member.spouse = None
            member.save()
            parents = (
                list(self.cleaned_data.get("parents", []))
                if "parents" in self.data
                else list(member.parents.all())
            )
            children = (
                list(self.cleaned_data.get("children", []))
                if "children" in self.data
                else list(member.children.all())
            )
            spouse_name = self.cleaned_data.get("spouse_name", "").strip()
            if spouse_name:
                spouse = self._create_placeholder(spouse_name)
                member.spouse = spouse
                member.save(update_fields=["spouse", "updated_at"])
            parents.extend(
                self._create_placeholders(
                    self.cleaned_data.get("parents_names", []), parents
                )
            )
            children.extend(
                self._create_placeholders(
                    self.cleaned_data.get("children_names", []), children
                )
            )
            if "parents" in self.data or self.cleaned_data.get("parents_names"):
                member.parents.set(parents)
            if "children" in self.data or self.cleaned_data.get("children_names"):
                member.children.set(children)
        return member

    @classmethod
    def _create_placeholders(cls, names, existing_members):
        existing_names = {
            f"{person.first_name} {person.last_name}".strip().casefold()
            for person in existing_members
        }
        placeholders = []
        for name in names:
            if name.casefold() in existing_names:
                continue
            placeholders.append(cls._create_placeholder(name))
            existing_names.add(name.casefold())
        return placeholders

    @staticmethod
    def _create_placeholder(full_name):
        first_name, _, last_name = full_name.partition(" ")
        return Member.objects.create(
            first_name=first_name,
            last_name=last_name,
            status=Member.Status.PENDING,
            is_placeholder=True,
        )
