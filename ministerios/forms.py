from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from membros.models import Member

from .models import (
    Department,
    DepartmentActivity,
    DepartmentActivityAssignment,
    DepartmentActivityAttendance,
    DepartmentMembership,
)


class DepartmentForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        label="Participantes",
        queryset=Member.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text=(
            "As pessoas escolhidas como líder ou vice-líder são incluídas "
            "automaticamente. Use Ctrl (Windows) ou Command (Mac) para selecionar várias."
        ),
    )

    class Meta:
        model = Department
        fields = ("name", "description", "leader", "vice_leader", "active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        eligible = Member.objects.filter(
            status__in=(Member.Status.MEMBER, Member.Status.CONGREGANT),
            is_placeholder=False,
            is_deceased=False,
        )
        self.fields["leader"].queryset = eligible
        self.fields["leader"].required = False
        self.fields["leader"].empty_label = "Nenhum responsável"
        self.fields["leader"].help_text = (
            "Opcional. Será incluído automaticamente com a função Líder."
        )
        self.fields["vice_leader"].queryset = eligible
        self.fields["vice_leader"].required = False
        self.fields["vice_leader"].empty_label = "Nenhum vice-líder"
        self.fields["vice_leader"].help_text = (
            "Opcional. Será incluído automaticamente com a função Vice-líder."
        )
        current_members = Member.objects.none()
        if self.instance.pk:
            current_members = self.instance.members.all()
            for field_name in ("leader", "vice_leader"):
                member_id = getattr(self.instance, f"{field_name}_id")
                if member_id:
                    self.fields[field_name].queryset = (
                        self.fields[field_name].queryset
                        | Member.objects.filter(pk=member_id)
                    ).distinct()
        self.fields["participants"].queryset = (
            eligible | current_members
        ).distinct()
        self.order_fields(
            ("name", "description", "leader", "vice_leader", "participants", "active")
        )
        if self.instance.pk:
            self.initial["participants"] = self.instance.members.exclude(
                pk__in=[
                    pk
                    for pk in (self.instance.leader_id, self.instance.vice_leader_id)
                    if pk
                ]
            )

    def clean(self):
        cleaned_data = super().clean()
        leader = cleaned_data.get("leader")
        vice_leader = cleaned_data.get("vice_leader")
        if leader and vice_leader and leader == vice_leader:
            self.add_error(
                "vice_leader", "A mesma pessoa não pode ser líder e vice-líder."
            )
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        department = super().save(commit=False)
        if commit:
            department.save()
            self._save_m2m_with_memberships()
        else:
            self.save_m2m = self._save_m2m_with_memberships
        return department

    @transaction.atomic
    def _save_m2m_with_memberships(self):
        super()._save_m2m()
        department = self.instance
        if not department.pk:
            raise ValueError("Salve o departamento antes de salvar seus participantes.")
        role_by_member_id = {
            member.pk: DepartmentMembership.Role.PARTICIPANT
            for member in self.cleaned_data.get("participants", [])
        }
        leader = self.cleaned_data.get("leader")
        vice_leader = self.cleaned_data.get("vice_leader")
        if leader:
            role_by_member_id[leader.pk] = DepartmentMembership.Role.LEADER
        if vice_leader:
            role_by_member_id[vice_leader.pk] = DepartmentMembership.Role.VICE_LEADER
        current_memberships = {
            membership.member_id: membership
            for membership in department.memberships.all()
        }
        DepartmentMembership.objects.filter(department=department).exclude(
            member_id__in=role_by_member_id
        ).delete()
        memberships_to_create = []
        for member_id, role in role_by_member_id.items():
            existing = current_memberships.get(member_id)
            if existing:
                if existing.role != role:
                    existing.role = role
                    existing.save(update_fields=["role"])
            else:
                memberships_to_create.append(
                    DepartmentMembership(
                        department=department,
                        member_id=member_id,
                        role=role,
                    )
                )
        DepartmentMembership.objects.bulk_create(memberships_to_create)


class DepartmentActivityForm(forms.ModelForm):
    class Meta:
        model = DepartmentActivity
        fields = (
            "title",
            "kind",
            "status",
            "starts_at",
            "ends_at",
            "location",
            "responsible",
            "participants",
            "description",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "description": forms.Textarea(attrs={"rows": 4}),
            "participants": forms.SelectMultiple(attrs={"size": 8}),
        }

    def __init__(self, *args, department, **kwargs):
        super().__init__(*args, **kwargs)
        self.department = department
        eligible_members = Member.objects.filter(
            pk__in=department.members.values("pk")
        ).order_by("first_name", "last_name")
        self.fields["responsible"].queryset = eligible_members
        self.fields["responsible"].required = False
        self.fields["responsible"].empty_label = "Nenhum responsável"
        self.fields["participants"].queryset = eligible_members
        self.fields["participants"].help_text = (
            "Selecione somente participantes deste departamento. Use Ctrl (Windows) "
            "ou Command (Mac) para selecionar mais de uma pessoa."
        )
        eligible_members = self.fields["responsible"].queryset
        for leader_id in (department.leader_id, department.vice_leader_id):
            if leader_id:
                eligible_members = eligible_members | Member.objects.filter(
                    pk=leader_id
                )
        self.fields["responsible"].queryset = eligible_members.distinct()
        if self.instance.pk:
            selected_members = self.instance.participants.all()
            self.fields["participants"].queryset = (
                self.fields["participants"].queryset | selected_members
            ).distinct()
            if self.instance.responsible_id:
                self.fields["responsible"].queryset = (
                    self.fields["responsible"].queryset
                    | Member.objects.filter(pk=self.instance.responsible_id)
                ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "O término deve ser posterior ao início.")
        return cleaned_data


class DepartmentAttendanceForm(forms.Form):
    def __init__(self, *args, activity, **kwargs):
        super().__init__(*args, **kwargs)
        self.activity = activity
        members_by_id = {
            member.pk: member
            for member in activity.participants.order_by("first_name", "last_name")
        }
        records = {
            record.member_id: record
            for record in activity.attendance_records.select_related("member")
        }
        members_by_id.update(
            {member_id: record.member for member_id, record in records.items()}
        )
        self.members = sorted(
            members_by_id.values(),
            key=lambda member: (member.first_name.casefold(), member.last_name.casefold()),
        )
        choices = [
            (DepartmentActivityAttendance.Status.PENDING, "Não registrado"),
            (DepartmentActivityAttendance.Status.PRESENT, "Presente"),
            (DepartmentActivityAttendance.Status.ABSENT, "Ausente"),
        ]
        for member in self.members:
            field_name = f"attendance_{member.pk}"
            self.fields[field_name] = forms.ChoiceField(
                label=str(member),
                choices=choices,
                initial=(
                    records[member.pk].status
                    if member.pk in records
                    else DepartmentActivityAttendance.Status.PENDING
                ),
            )

    @transaction.atomic
    def save(self):
        for member in self.members:
            status = self.cleaned_data[f"attendance_{member.pk}"]
            DepartmentActivityAttendance.objects.update_or_create(
                activity=self.activity,
                member=member,
                defaults={"status": status},
            )


class DepartmentActivityAssignmentForm(forms.ModelForm):
    class Meta:
        model = DepartmentActivityAssignment
        fields = ("member", "role", "custom_role")

    def __init__(self, *args, activity, **kwargs):
        super().__init__(*args, **kwargs)
        self.activity = activity
        self.fields["member"].queryset = activity.department.members.order_by(
            "first_name", "last_name"
        )
        self.fields["member"].empty_label = "Selecione uma pessoa"
        self.fields["custom_role"].required = False
        self.fields["custom_role"].help_text = (
            'Preencha somente quando selecionar "Outra função".'
        )
        self.fields["custom_role"].widget.attrs["placeholder"] = (
            "Ex.: operador de som"
        )

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        custom_role = cleaned_data.get("custom_role", "").strip()
        member = cleaned_data.get("member")
        if role == DepartmentActivityAssignment.Role.OTHER and not custom_role:
            self.add_error(
                "custom_role", "Descreva a função quando selecionar Outra função."
            )
        elif role != DepartmentActivityAssignment.Role.OTHER and custom_role:
            self.add_error(
                "custom_role", "Preencha este campo somente para Outra função."
            )
        elif member and role and DepartmentActivityAssignment.objects.filter(
            activity=self.activity,
            member=member,
            role=role,
            custom_role=custom_role,
        ).exists():
            raise ValidationError(
                "Esta pessoa já está escalada para esta função nesta atividade."
            )
        return cleaned_data

    def save(self, commit=True):
        assignment = super().save(commit=False)
        assignment.activity = self.activity
        if commit:
            assignment.save()
        return assignment
