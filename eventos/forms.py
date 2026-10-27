from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from membros.models import Member

from .models import (
    ChurchEvent,
    ChurchSpace,
    EventAssignment,
    EventProgramItem,
    EventRegistration,
    SpaceReservation,
)


class EventForm(forms.ModelForm):
    class Meta:
        model = ChurchEvent
        fields = (
            "title",
            "kind",
            "status",
            "description",
            "starts_at",
            "ends_at",
            "location",
            "registration_open",
            "capacity",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("registration_open") and cleaned_data.get("status") != ChurchEvent.Status.PUBLISHED:
            self.add_error(
                "registration_open",
                "Publique o evento antes de abrir as inscrições.",
            )
        return cleaned_data


class EventBoundForm(forms.ModelForm):
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event


class EventProgramItemForm(EventBoundForm):
    class Meta:
        model = EventProgramItem
        fields = ("title", "starts_at", "details", "position")
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            )
        }

    def clean_starts_at(self):
        starts_at = self.cleaned_data["starts_at"]
        if self.event and not self.event.starts_at <= starts_at <= self.event.ends_at:
            raise ValidationError("A atividade deve ocorrer dentro do período do evento.")
        return starts_at


class EventAssignmentForm(EventBoundForm):
    class Meta:
        model = EventAssignment
        fields = ("member", "role", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = Member.objects.order_by("first_name", "last_name")

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get("member")
        role = cleaned_data.get("role")
        if self.event and member and role and EventAssignment.objects.filter(
            event=self.event, member=member, role=role
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Essa pessoa já está escalada para essa função.")
        return cleaned_data


class EventRegistrationForm(EventBoundForm):
    class Meta:
        model = EventRegistration
        fields = ("member", "attendee_name", "attendee_contact")
        widgets = {
            "attendee_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "attendee_contact": forms.TextInput(attrs={"autocomplete": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = Member.objects.order_by("first_name", "last_name")
        self.fields["member"].required = False
        self.fields["member"].help_text = (
            "Selecione uma pessoa cadastrada ou preencha o nome do visitante."
        )

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get("member")
        attendee_name = cleaned_data.get("attendee_name", "").strip()
        if not member and not attendee_name:
            self.add_error("attendee_name", "Informe um nome ou selecione uma pessoa cadastrada.")
        if self.event and member and EventRegistration.objects.filter(
            event=self.event, member=member
        ).exclude(pk=self.instance.pk).exists():
            self.add_error("member", "Essa pessoa já está inscrita neste evento.")
        return cleaned_data


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = EventRegistration
        fields = ("attended",)


class SpaceReservationForm(forms.ModelForm):
    class Meta:
        model = SpaceReservation
        fields = ("space", "event", "purpose", "starts_at", "ends_at", "status", "notes")
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_spaces = Q(active=True)
        if self.instance.pk:
            active_spaces |= Q(pk=self.instance.space_id)
        self.fields["space"].queryset = ChurchSpace.objects.filter(active_spaces)
        self.fields["event"].queryset = ChurchEvent.objects.exclude(
            status=ChurchEvent.Status.CANCELLED
        )
        self.fields["event"].required = False
