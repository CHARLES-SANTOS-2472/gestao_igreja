from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from membros.models import Member

from .models import (
    ChurchEvent,
    ChurchSpace,
    EventProgramItem,
    EventRegistration,
    SpaceReservation,
)


class EventManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="agenda", password="senha-segura-teste"
        )
        permissions = Permission.objects.filter(
            content_type__app_label="eventos",
            codename__in=(
                "view_churchevent",
                "add_churchevent",
                "change_churchevent",
                "add_eventprogramitem",
                "add_eventassignment",
                "view_eventassignment",
                "add_eventregistration",
                "view_eventregistration",
                "change_eventregistration",
                "view_spacereservation",
                "add_spacereservation",
                "change_spacereservation",
            ),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)
        self.start = (timezone.now() + timedelta(days=10)).replace(
            minute=0, second=0, microsecond=0
        )
        self.end = self.start + timedelta(hours=3)

    def create_event(self):
        return ChurchEvent.objects.create(
            title="Culto de celebração",
            kind=ChurchEvent.Kind.SERVICE,
            status=ChurchEvent.Status.PUBLISHED,
            starts_at=self.start,
            ends_at=self.end,
            location="Templo principal",
            registration_open=True,
        )

    def test_event_creation_and_listing(self):
        response = self.client.post(
            reverse("event-create"),
            {
                "title": "Culto de celebração",
                "kind": ChurchEvent.Kind.SERVICE,
                "status": ChurchEvent.Status.PUBLISHED,
                "starts_at": timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": timezone.localtime(self.end).strftime("%Y-%m-%dT%H:%M"),
                "location": "Templo principal",
                "registration_open": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        event = ChurchEvent.objects.get(title="Culto de celebração")
        self.assertEqual(event.created_by, self.user)
        self.assertEqual(
            self.client.get(reverse("event-list")).status_code,
            200,
        )

    def test_event_cannot_end_before_it_starts(self):
        response = self.client.post(
            reverse("event-create"),
            {
                "title": "Horários inválidos",
                "kind": ChurchEvent.Kind.SERVICE,
                "status": ChurchEvent.Status.DRAFT,
                "starts_at": timezone.localtime(self.end).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("ends_at", response.context["form"].errors)
        self.assertFalse(ChurchEvent.objects.filter(title="Horários inválidos").exists())

    def test_program_item_must_fall_inside_event_window(self):
        event = self.create_event()

        response = self.client.post(
            reverse("program-item-create", kwargs={"event_pk": event.pk}),
            {
                "title": "Abertura",
                "starts_at": timezone.localtime(self.end + timedelta(minutes=1)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "position": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("starts_at", response.context["form"].errors)
        self.assertFalse(EventProgramItem.objects.filter(event=event).exists())

    def test_registration_and_attendance_are_recorded(self):
        event = self.create_event()
        member = Member.objects.create(first_name="Rute", last_name="Lima")

        response = self.client.post(
            reverse("registration-create", kwargs={"event_pk": event.pk}),
            {"member": member.pk, "attendee_name": "", "attendee_contact": ""},
        )

        self.assertEqual(response.status_code, 302)
        registration = EventRegistration.objects.get(event=event, member=member)
        attendance_response = self.client.post(
            reverse("attendance-update", kwargs={"pk": registration.pk}),
            {"attended": "on"},
        )

        self.assertEqual(attendance_response.status_code, 302)
        registration.refresh_from_db()
        self.assertTrue(registration.attended)

    def test_overlapping_space_reservation_is_rejected(self):
        event = self.create_event()
        space = ChurchSpace.objects.create(name="Salão social", kind=ChurchSpace.Kind.HALL)
        SpaceReservation.objects.create(
            space=space,
            event=event,
            purpose="Culto",
            starts_at=self.start,
            ends_at=self.end,
        )

        response = self.client.post(
            reverse("reservation-create"),
            {
                "space": space.pk,
                "event": event.pk,
                "purpose": "Reunião",
                "starts_at": timezone.localtime(
                    self.start + timedelta(minutes=30)
                ).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": timezone.localtime(
                    self.end + timedelta(minutes=30)
                ).strftime("%Y-%m-%dT%H:%M"),
                "status": SpaceReservation.Status.RESERVED,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("space", response.context["form"].errors)
        self.assertEqual(SpaceReservation.objects.filter(space=space).count(), 1)

    def test_overlapping_reservation_can_be_cancelled(self):
        event = self.create_event()
        space = ChurchSpace.objects.create(name="Sala multiuso")
        reservation = SpaceReservation.objects.create(
            space=space,
            event=event,
            purpose="Encontro",
            starts_at=self.start,
            ends_at=self.end,
        )

        response = self.client.post(
            reverse("reservation-update", kwargs={"pk": reservation.pk}),
            {
                "space": space.pk,
                "event": event.pk,
                "purpose": "Encontro",
                "starts_at": timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": timezone.localtime(self.end).strftime("%Y-%m-%dT%H:%M"),
                "status": SpaceReservation.Status.CANCELLED,
            },
        )

        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, SpaceReservation.Status.CANCELLED)

    def test_reservation_form_can_be_opened_from_event(self):
        event = self.create_event()

        response = self.client.get(
            reverse("reservation-create"), {"event": event.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["event"].value(), event.pk)

    def test_event_view_does_not_expose_registrants_without_permission(self):
        event = self.create_event()
        EventRegistration.objects.create(event=event, attendee_name="Visitante privado")
        user = get_user_model().objects.create_user(username="consulta-agenda")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="eventos", codename="view_churchevent"
            )
        )
        self.client.force_login(user)

        response = self.client.get(reverse("event-detail", kwargs={"pk": event.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["registrations"])
        self.assertNotContains(response, "Visitante privado")

    def test_event_pages_require_permission(self):
        user = get_user_model().objects.create_user(username="sem-permissao")
        self.client.force_login(user)

        response = self.client.get(reverse("event-list"))

        self.assertEqual(response.status_code, 403)
