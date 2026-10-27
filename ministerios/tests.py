from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from membros.models import Member

from .forms import DepartmentForm
from .models import (
    Department,
    DepartmentActivity,
    DepartmentActivityAssignment,
    DepartmentActivityAttendance,
    DepartmentMembership,
)


class DepartmentManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lideranca")
        permissions = Permission.objects.filter(
            content_type__app_label="ministerios",
            codename__in=(
                "view_department",
                "add_department",
                "change_department",
                "view_departmentactivity",
                "add_departmentactivity",
                "change_departmentactivity",
                "view_departmentattendance",
                "manage_departmentattendance",
                "manage_departmentactivityscales",
            ),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)

    def test_create_department_links_selected_members_and_leader(self):
        leader = Member.objects.create(first_name="Ana", last_name="Lima")
        volunteer = Member.objects.create(first_name="João", last_name="Souza")

        response = self.client.post(
            reverse("department-create"),
            {
                "name": "Louvor",
                "description": "Equipe de música.",
                "leader": leader.pk,
                "vice_leader": "",
                "participants": [volunteer.pk],
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        department = Department.objects.get(name="Louvor")
        self.assertEqual(department.leader, leader)
        self.assertSetEqual(
            set(department.members.values_list("pk", flat=True)),
            {leader.pk, volunteer.pk},
        )
        roles = dict(
            department.memberships.values_list("member_id", "role")
        )
        self.assertEqual(roles[leader.pk], "leader")
        self.assertEqual(roles[volunteer.pk], "participant")

    def test_update_can_remove_a_member_and_clear_leader(self):
        leader = Member.objects.create(first_name="Marta")
        volunteer = Member.objects.create(first_name="Pedro")
        department = Department.objects.create(name="Ação social", leader=leader)
        department.members.add(leader, volunteer)

        response = self.client.post(
            reverse("department-update", kwargs={"pk": department.pk}),
            {
                "name": department.name,
                "description": "",
                "leader": "",
                "vice_leader": "",
                "participants": [volunteer.pk],
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        department.refresh_from_db()
        self.assertIsNone(department.leader)
        self.assertSetEqual(
            set(department.members.values_list("pk", flat=True)), {volunteer.pk}
        )
        self.assertEqual(
            department.memberships.get(member=volunteer).role, "participant"
        )

    def test_create_department_assigns_standard_leadership_roles(self):
        leader = Member.objects.create(first_name="Ana")
        vice_leader = Member.objects.create(first_name="Bruna")
        participant = Member.objects.create(first_name="Carla")

        response = self.client.post(
            reverse("department-create"),
            {
                "name": "Missões",
                "leader": leader.pk,
                "vice_leader": vice_leader.pk,
                "participants": [participant.pk],
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        department = Department.objects.get(name="Missões")
        self.assertEqual(department.vice_leader, vice_leader)
        self.assertSetEqual(
            set(
                department.memberships.values_list("member_id", "role")
            ),
            {
                (leader.pk, DepartmentMembership.Role.LEADER),
                (vice_leader.pk, DepartmentMembership.Role.VICE_LEADER),
                (participant.pk, DepartmentMembership.Role.PARTICIPANT),
            },
        )

    def test_department_form_save_m2m_records_roles_after_commit_false(self):
        leader = Member.objects.create(first_name="Gabriela")
        participant = Member.objects.create(first_name="Isabel")
        form = DepartmentForm(
            data={
                "name": "Ação social",
                "leader": leader.pk,
                "vice_leader": "",
                "participants": [participant.pk],
                "active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        department = form.save(commit=False)
        department.save()
        form.save_m2m()

        self.assertEqual(
            department.memberships.get(member=leader).role,
            DepartmentMembership.Role.LEADER,
        )
        self.assertEqual(
            department.memberships.get(member=participant).role,
            DepartmentMembership.Role.PARTICIPANT,
        )

    def test_department_form_prevents_same_person_as_leader_and_vice_leader(self):
        member = Member.objects.create(first_name="Débora")

        response = self.client.post(
            reverse("department-create"),
            {
                "name": "Infantil",
                "leader": member.pk,
                "vice_leader": member.pk,
                "participants": [],
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("vice_leader", response.context["form"].errors)
        self.assertFalse(Department.objects.filter(name="Infantil").exists())

    def test_changing_leader_assigns_roles_on_department_memberships(self):
        previous_leader = Member.objects.create(first_name="Ester")
        next_leader = Member.objects.create(first_name="Flávia")
        department = Department.objects.create(
            name="Louvor", leader=previous_leader
        )
        department.members.add(previous_leader, next_leader)
        DepartmentMembership.objects.filter(
            department=department, member=previous_leader
        ).update(role=DepartmentMembership.Role.LEADER)

        response = self.client.post(
            reverse("department-update", kwargs={"pk": department.pk}),
            {
                "name": department.name,
                "description": "",
                "leader": next_leader.pk,
                "vice_leader": "",
                "participants": [previous_leader.pk],
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        department.refresh_from_db()
        self.assertEqual(department.leader, next_leader)
        self.assertEqual(
            department.memberships.get(member=previous_leader).role,
            DepartmentMembership.Role.PARTICIPANT,
        )
        self.assertEqual(
            department.memberships.get(member=next_leader).role,
            DepartmentMembership.Role.LEADER,
        )

    def test_department_list_can_search_by_member_and_filter_active(self):
        member = Member.objects.create(first_name="Rute", last_name="Alves")
        active = Department.objects.create(name="Intercessão")
        active.members.add(member)
        Department.objects.create(name="Antigo ministério", active=False)

        response = self.client.get(
            reverse("department-list"), {"q": "Rute", "active": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["departments"], [active], transform=lambda item: item
        )

    def test_department_list_shows_description_with_two_line_style(self):
        description = (
            "Uma descrição completa e detalhada para apresentar o propósito "
            "do Ministério Infantil em duas linhas na listagem."
        )
        Department.objects.create(name="Ministério Infantil", description=description)

        response = self.client.get(reverse("department-list"))

        self.assertContains(response, 'class="subline department-description"')
        self.assertContains(response, description)

    def test_department_pages_require_login_and_permission(self):
        self.client.logout()
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, 302)

        user_without_permission = get_user_model().objects.create_user(
            username="sem_acesso"
        )
        self.client.force_login(user_without_permission)
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, 403)

    def test_department_form_excludes_visitors_and_incomplete_profiles(self):
        visitor = Member.objects.create(
            first_name="Visitante", status=Member.Status.VISITOR
        )
        incomplete = Member.objects.create(
            first_name="Incompleto",
            status=Member.Status.PENDING,
            is_placeholder=True,
        )

        response = self.client.get(reverse("department-create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertNotIn(visitor, form.fields["participants"].queryset)
        self.assertNotIn(incomplete, form.fields["participants"].queryset)
        self.assertNotIn(visitor, form.fields["leader"].queryset)
        self.assertNotIn(incomplete, form.fields["vice_leader"].queryset)

    def test_department_detail_displays_each_membership_role(self):
        leader = Member.objects.create(first_name="Laura")
        vice_leader = Member.objects.create(first_name="Marina")
        participant = Member.objects.create(first_name="Nicolas")
        department = Department.objects.create(
            name="Intercessão", leader=leader, vice_leader=vice_leader
        )
        DepartmentMembership.objects.create(
            department=department,
            member=leader,
            role=DepartmentMembership.Role.LEADER,
        )
        DepartmentMembership.objects.create(
            department=department,
            member=vice_leader,
            role=DepartmentMembership.Role.VICE_LEADER,
        )
        DepartmentMembership.objects.create(
            department=department,
            member=participant,
            role=DepartmentMembership.Role.PARTICIPANT,
        )

        response = self.client.get(
            reverse("department-detail", kwargs={"pk": department.pk})
        )

        self.assertContains(response, "Líder")
        self.assertContains(response, "Vice-líder")
        self.assertContains(response, "Participante")

    def test_department_view_does_not_expose_member_contact_without_member_permission(self):
        member = Member.objects.create(
            first_name="Raquel", mobile="11987654321"
        )
        department = Department.objects.create(name="Infantil")
        department.members.add(member)

        response = self.client.get(
            reverse("department-detail", kwargs={"pk": department.pk})
        )

        self.assertContains(response, "Raquel")
        self.assertNotContains(response, member.mobile)

    def test_create_activity_links_department_responsible_and_participants(self):
        leader = Member.objects.create(first_name="Ana", last_name="Lima")
        participant = Member.objects.create(first_name="João", last_name="Souza")
        department = Department.objects.create(name="Louvor", leader=leader)
        department.members.add(participant)

        response = self.client.post(
            reverse(
                "department-activity-create",
                kwargs={"department_pk": department.pk},
            ),
            {
                "title": "Ensaio de domingo",
                "kind": DepartmentActivity.Kind.REHEARSAL,
                "status": DepartmentActivity.Status.PLANNED,
                "starts_at": "2026-10-25T16:00",
                "ends_at": "2026-10-25T18:00",
                "location": "Templo",
                "responsible": leader.pk,
                "participants": [participant.pk],
                "description": "Preparação do repertório.",
            },
        )

        self.assertEqual(response.status_code, 302)
        activity = DepartmentActivity.objects.get(title="Ensaio de domingo")
        self.assertEqual(activity.department, department)
        self.assertEqual(activity.responsible, leader)
        self.assertSetEqual(
            set(activity.participants.values_list("pk", flat=True)),
            {participant.pk},
        )
        self.assertEqual(
            activity.starts_at,
            timezone.make_aware(datetime(2026, 10, 25, 16, 0)),
        )

    def test_activity_rejects_end_before_start(self):
        department = Department.objects.create(name="Jovens")

        response = self.client.post(
            reverse(
                "department-activity-create",
                kwargs={"department_pk": department.pk},
            ),
            {
                "title": "Reunião de jovens",
                "kind": DepartmentActivity.Kind.MEETING,
                "status": DepartmentActivity.Status.PLANNED,
                "starts_at": "2026-10-25T18:00",
                "ends_at": "2026-10-25T17:00",
                "location": "Sala 2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("ends_at", response.context["form"].errors)
        self.assertFalse(DepartmentActivity.objects.exists())

    def test_activity_form_only_allows_department_members_as_participants(self):
        department_member = Member.objects.create(first_name="Priscila")
        outsider = Member.objects.create(first_name="Visitante")
        department = Department.objects.create(name="Intercessão")
        department.members.add(department_member)

        response = self.client.post(
            reverse(
                "department-activity-create",
                kwargs={"department_pk": department.pk},
            ),
            {
                "title": "Encontro de oração",
                "kind": DepartmentActivity.Kind.MEETING,
                "status": DepartmentActivity.Status.PLANNED,
                "starts_at": "2026-10-25T18:00",
                "participants": [outsider.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("participants", response.context["form"].errors)
        self.assertFalse(DepartmentActivity.objects.exists())

    def test_activity_edit_is_scoped_to_department(self):
        department = Department.objects.create(name="Infantil")
        other_department = Department.objects.create(name="Louvor")
        activity = DepartmentActivity.objects.create(
            department=other_department,
            title="Encontro",
            starts_at=timezone.now(),
        )

        response = self.client.get(
            reverse(
                "department-activity-update",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_activity_pages_require_specific_permissions(self):
        department = Department.objects.create(name="Missões")
        user = get_user_model().objects.create_user(username="sem_atividade")
        user_permissions = Permission.objects.filter(
            content_type__app_label="ministerios",
            codename__in=("view_department", "add_department", "change_department"),
        )
        user.user_permissions.add(*user_permissions)
        self.client.force_login(user)

        response = self.client.get(
            reverse(
                "department-activity-create",
                kwargs={"department_pk": department.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_scale_assignment_can_be_added_and_is_shown_on_activity(self):
        member = Member.objects.create(first_name="Ana", last_name="Silva")
        department = Department.objects.create(name="Louvor")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Culto de domingo",
            starts_at=timezone.now(),
        )

        response = self.client.post(
            reverse(
                "department-activity-scale",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
            {
                "member": member.pk,
                "role": DepartmentActivityAssignment.Role.MUSICIAN,
                "custom_role": "",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "department-activity-scale",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
        )
        assignment = DepartmentActivityAssignment.objects.get(activity=activity)
        self.assertEqual(assignment.member, member)
        self.assertEqual(assignment.role_label, "Músico(a)")
        detail_response = self.client.get(
            reverse(
                "department-activity-detail",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )
        self.assertContains(detail_response, "Escala de funções")
        self.assertContains(detail_response, "Músico(a)")
        self.assertContains(detail_response, "Ana Silva")

    def test_scale_accepts_custom_roles_and_rejects_empty_custom_role(self):
        member = Member.objects.create(first_name="Bruna")
        department = Department.objects.create(name="Louvor")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Culto especial",
            starts_at=timezone.now(),
        )
        url = reverse(
            "department-activity-scale",
            kwargs={"department_pk": department.pk, "pk": activity.pk},
        )

        invalid_response = self.client.post(
            url,
            {
                "member": member.pk,
                "role": DepartmentActivityAssignment.Role.OTHER,
                "custom_role": "",
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertIn("custom_role", invalid_response.context["form"].errors)
        self.assertFalse(DepartmentActivityAssignment.objects.exists())

        valid_response = self.client.post(
            url,
            {
                "member": member.pk,
                "role": DepartmentActivityAssignment.Role.OTHER,
                "custom_role": "Operadora de som",
            },
        )
        self.assertEqual(valid_response.status_code, 302)
        self.assertEqual(
            DepartmentActivityAssignment.objects.get(activity=activity).role_label,
            "Operadora de som",
        )

    def test_scale_rejects_non_department_members_and_duplicate_roles(self):
        member = Member.objects.create(first_name="Carla")
        outsider = Member.objects.create(first_name="Visitante")
        department = Department.objects.create(name="Recepção")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Culto",
            starts_at=timezone.now(),
        )
        url = reverse(
            "department-activity-scale",
            kwargs={"department_pk": department.pk, "pk": activity.pk},
        )
        payload = {
            "member": outsider.pk,
            "role": DepartmentActivityAssignment.Role.RECEPTION,
            "custom_role": "",
        }

        outsider_response = self.client.post(url, payload)
        self.assertEqual(outsider_response.status_code, 200)
        self.assertIn("member", outsider_response.context["form"].errors)
        self.assertFalse(DepartmentActivityAssignment.objects.exists())

        payload["member"] = member.pk
        self.client.post(url, payload)
        duplicate_response = self.client.post(url, payload)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(DepartmentActivityAssignment.objects.count(), 1)
        self.assertContains(
            duplicate_response,
            "Esta pessoa já está escalada para esta função nesta atividade.",
        )
        invalid_assignment = DepartmentActivityAssignment(
            activity=activity,
            member=outsider,
            role=DepartmentActivityAssignment.Role.RECEPTION,
        )
        with self.assertRaises(ValidationError):
            invalid_assignment.full_clean()

    def test_scale_assignment_can_only_be_removed_with_post(self):
        member = Member.objects.create(first_name="Davi")
        department = Department.objects.create(name="Apoio")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Culto",
            starts_at=timezone.now(),
        )
        assignment = DepartmentActivityAssignment.objects.create(
            activity=activity,
            member=member,
            role=DepartmentActivityAssignment.Role.SUPPORT,
        )
        url = reverse(
            "department-activity-assignment-delete",
            kwargs={
                "department_pk": department.pk,
                "pk": activity.pk,
                "assignment_pk": assignment.pk,
            },
        )

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(
            DepartmentActivityAssignment.objects.filter(pk=assignment.pk).exists()
        )

        post_response = self.client.post(url)
        self.assertRedirects(
            post_response,
            reverse(
                "department-activity-scale",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
        )
        self.assertFalse(
            DepartmentActivityAssignment.objects.filter(pk=assignment.pk).exists()
        )

    def test_scale_management_requires_its_own_permission(self):
        member = Member.objects.create(first_name="Elisa")
        department = Department.objects.create(name="Infantil")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Culto infantil",
            starts_at=timezone.now(),
        )
        user = get_user_model().objects.create_user(username="sem_escala")
        user_permissions = Permission.objects.filter(
            content_type__app_label="ministerios",
            codename="view_departmentactivity",
        )
        user.user_permissions.add(*user_permissions)
        self.client.force_login(user)

        response = self.client.get(
            reverse(
                "department-activity-scale",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_department_detail_shows_activity_link_when_permitted(self):
        department = Department.objects.create(name="Infantil")

        response = self.client.get(
            reverse("department-detail", kwargs={"pk": department.pk})
        )

        self.assertContains(response, "Reuniões e atividades")
        self.assertContains(response, "Nova atividade")

    def test_attendance_can_be_registered_for_each_activity_participant(self):
        first = Member.objects.create(first_name="Ana")
        second = Member.objects.create(first_name="Bruno")
        department = Department.objects.create(name="Jovens")
        department.members.add(first, second)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Encontro de jovens",
            starts_at=timezone.now(),
        )
        activity.participants.add(first, second)

        response = self.client.post(
            reverse(
                "department-activity-attendance",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
            {
                f"attendance_{first.pk}": DepartmentActivityAttendance.Status.PRESENT,
                f"attendance_{second.pk}": DepartmentActivityAttendance.Status.ABSENT,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "department-activity-detail",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
        )
        self.assertEqual(
            DepartmentActivityAttendance.objects.get(
                activity=activity, member=first
            ).status,
            DepartmentActivityAttendance.Status.PRESENT,
        )
        self.assertEqual(
            DepartmentActivityAttendance.objects.get(
                activity=activity, member=second
            ).status,
            DepartmentActivityAttendance.Status.ABSENT,
        )

    def test_attendance_can_be_reset_to_unrecorded(self):
        member = Member.objects.create(first_name="Lívia")
        department = Department.objects.create(name="Infantil")
        department.members.add(member)
        activity = DepartmentActivity.objects.create(
            department=department, title="Reunião", starts_at=timezone.now()
        )
        activity.participants.add(member)
        DepartmentActivityAttendance.objects.create(
            activity=activity,
            member=member,
            status=DepartmentActivityAttendance.Status.PRESENT,
        )

        response = self.client.post(
            reverse(
                "department-activity-attendance",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            ),
            {
                f"attendance_{member.pk}": DepartmentActivityAttendance.Status.PENDING
            },
        )

        self.assertEqual(response.status_code, 302)
        record = DepartmentActivityAttendance.objects.get(
            activity=activity, member=member
        )
        self.assertEqual(record.status, DepartmentActivityAttendance.Status.PENDING)

    def test_attendance_form_displays_existing_statuses(self):
        present_member = Member.objects.create(first_name="Helena")
        pending_member = Member.objects.create(first_name="Marcos")
        department = Department.objects.create(name="Intercessão")
        department.members.add(present_member, pending_member)
        activity = DepartmentActivity.objects.create(
            department=department, title="Oração", starts_at=timezone.now()
        )
        activity.participants.add(present_member, pending_member)
        DepartmentActivityAttendance.objects.create(
            activity=activity,
            member=present_member,
            status=DepartmentActivityAttendance.Status.PRESENT,
        )

        response = self.client.get(
            reverse(
                "department-activity-attendance",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(
            form[f"attendance_{present_member.pk}"].value(),
            DepartmentActivityAttendance.Status.PRESENT,
        )
        self.assertEqual(
            form[f"attendance_{pending_member.pk}"].value(),
            DepartmentActivityAttendance.Status.PENDING,
        )

    def test_activity_detail_shows_attendance_button_to_authorized_user(self):
        department = Department.objects.create(name="Louvor")
        activity = DepartmentActivity.objects.create(
            department=department, title="Ensaio", starts_at=timezone.now()
        )

        response = self.client.get(
            reverse(
                "department-activity-detail",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar presença")
        self.assertContains(response, "0 registro(s) de presença")

    def test_attendance_report_summarizes_present_absent_pending_and_rate(self):
        present_member = Member.objects.create(first_name="Ana")
        absent_member = Member.objects.create(first_name="Bruno")
        pending_member = Member.objects.create(first_name="Clara")
        department = Department.objects.create(name="Louvor")
        department.members.add(present_member, absent_member, pending_member)
        activity = DepartmentActivity.objects.create(
            department=department,
            title="Ensaio",
            starts_at=timezone.now(),
        )
        activity.participants.add(present_member, absent_member, pending_member)
        DepartmentActivityAttendance.objects.create(
            activity=activity,
            member=present_member,
            status=DepartmentActivityAttendance.Status.PRESENT,
        )
        DepartmentActivityAttendance.objects.create(
            activity=activity,
            member=absent_member,
            status=DepartmentActivityAttendance.Status.ABSENT,
        )

        response = self.client.get(
            reverse(
                "department-attendance-report",
                kwargs={"pk": department.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        row = response.context["report_rows"][0]
        self.assertEqual(
            (row["total"], row["present"], row["absent"], row["pending"], row["rate"]),
            (3, 1, 1, 1, 33),
        )

    def test_attendance_cannot_be_registered_for_activity_from_another_department(self):
        department = Department.objects.create(name="Infantil")
        other_department = Department.objects.create(name="Louvor")
        activity = DepartmentActivity.objects.create(
            department=other_department,
            title="Ensaio",
            starts_at=timezone.now(),
        )

        response = self.client.get(
            reverse(
                "department-activity-attendance",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_attendance_requires_its_own_permission(self):
        department = Department.objects.create(name="Missões")
        activity = DepartmentActivity.objects.create(
            department=department, title="Reunião", starts_at=timezone.now()
        )
        user = get_user_model().objects.create_user(username="sem_presenca")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="ministerios",
                codename="view_departmentactivity",
            )
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse(
                "department-activity-attendance",
                kwargs={"department_pk": department.pk, "pk": activity.pk},
            )
        )

        self.assertEqual(response.status_code, 403)
