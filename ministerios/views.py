from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    DepartmentActivityAssignmentForm,
    DepartmentActivityForm,
    DepartmentAttendanceForm,
    DepartmentForm,
)
from .models import (
    Department,
    DepartmentActivity,
    DepartmentActivityAssignment,
    DepartmentActivityAttendance,
)


class DepartmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Department
    template_name = "ministerios/department_list.html"
    context_object_name = "departments"
    permission_required = "ministerios.view_department"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Department.objects.select_related("leader", "vice_leader")
            .annotate(member_count=Count("members", distinct=True))
            .order_by("name")
        )
        query = self.request.GET.get("q", "").strip()
        active = self.request.GET.get("active", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(leader__first_name__icontains=query)
                | Q(leader__last_name__icontains=query)
                | Q(vice_leader__first_name__icontains=query)
                | Q(vice_leader__last_name__icontains=query)
                | Q(memberships__member__first_name__icontains=query)
                | Q(memberships__member__last_name__icontains=query)
            ).distinct()
        if active == "true":
            queryset = queryset.filter(active=True)
        elif active == "false":
            queryset = queryset.filter(active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_active"] = self.request.GET.get("active", "").strip()
        return context


class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "ministerios/department_form.html"
    permission_required = "ministerios.add_department"

    def form_valid(self, form):
        messages.success(self.request, "Departamento cadastrado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("department-detail", kwargs={"pk": self.object.pk})


class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "ministerios/department_form.html"
    permission_required = "ministerios.change_department"

    def form_valid(self, form):
        messages.success(self.request, "Departamento atualizado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("department-detail", kwargs={"pk": self.object.pk})


class DepartmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Department
    template_name = "ministerios/department_detail.html"
    context_object_name = "department"
    permission_required = "ministerios.view_department"

    def get_queryset(self):
        return Department.objects.select_related(
            "leader", "vice_leader"
        ).prefetch_related("members", "memberships__member")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = self.object.memberships.select_related("member")
        if self.request.user.has_perm("ministerios.view_departmentactivity"):
            context["activities"] = self.object.activities.select_related(
                "responsible"
            ).annotate(
                participant_count=Count("participants", distinct=True),
                attendance_record_count=Count("attendance_records", distinct=True),
                attendance_present_count=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status=DepartmentActivityAttendance.Status.PRESENT
                    ),
                    distinct=True,
                ),
            ).prefetch_related("participants")
        context["show_attendance_report"] = self.request.user.has_perm(
            "ministerios.view_departmentattendance"
        )
        return context


class DepartmentActivityMixin(LoginRequiredMixin, PermissionRequiredMixin):
    form_class = DepartmentActivityForm

    def get_department(self):
        if not hasattr(self, "_department"):
            self._department = get_object_or_404(
                Department, pk=self.kwargs["department_pk"]
            )
        return self._department

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["department"] = self.get_department()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["department"] = self.get_department()
        return context


class DepartmentActivityCreateView(DepartmentActivityMixin, CreateView):
    model = DepartmentActivity
    template_name = "ministerios/activity_form.html"
    permission_required = "ministerios.add_departmentactivity"

    def form_valid(self, form):
        form.instance.department = self.get_department()
        messages.success(self.request, "Reunião ou atividade cadastrada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "department-activity-detail",
            kwargs={"department_pk": self.get_department().pk, "pk": self.object.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Nova reunião ou atividade"
        return context


class DepartmentActivityUpdateView(DepartmentActivityMixin, UpdateView):
    model = DepartmentActivity
    template_name = "ministerios/activity_form.html"
    permission_required = "ministerios.change_departmentactivity"

    def get_queryset(self):
        return DepartmentActivity.objects.filter(
            department_id=self.kwargs["department_pk"]
        )

    def form_valid(self, form):
        messages.success(self.request, "Reunião ou atividade atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "department-activity-detail",
            kwargs={
                "department_pk": self.object.department_id,
                "pk": self.object.pk,
            },
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Editar reunião ou atividade"
        return context


class DepartmentActivityDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = DepartmentActivity
    template_name = "ministerios/activity_detail.html"
    context_object_name = "activity"
    permission_required = "ministerios.view_departmentactivity"

    def get_queryset(self):
        return DepartmentActivity.objects.select_related(
            "department", "responsible"
        ).annotate(
            attendance_record_count=Count("attendance_records", distinct=True)
        ).prefetch_related("participants", "attendance_records").filter(
            department_id=self.kwargs["department_pk"]
        ).prefetch_related("assignments__member")


class DepartmentActivityAttendanceView(
    LoginRequiredMixin, PermissionRequiredMixin, FormView
):
    template_name = "ministerios/activity_attendance_form.html"
    form_class = DepartmentAttendanceForm
    permission_required = "ministerios.manage_departmentattendance"

    def get_activity(self):
        if not hasattr(self, "_activity"):
            self._activity = get_object_or_404(
                DepartmentActivity.objects.select_related("department").prefetch_related(
                    "participants", "attendance_records__member"
                ),
                pk=self.kwargs["pk"],
                department_id=self.kwargs["department_pk"],
            )
        return self._activity

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["activity"] = self.get_activity()
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Presenças atualizadas.")
        return super().form_valid(form)

    def get_success_url(self):
        activity = self.get_activity()
        return reverse(
            "department-activity-detail",
            kwargs={"department_pk": activity.department_id, "pk": activity.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"] = self.get_activity()
        context["department"] = context["activity"].department
        return context


class DepartmentActivityScaleView(
    LoginRequiredMixin, PermissionRequiredMixin, FormView
):
    template_name = "ministerios/activity_scale_form.html"
    form_class = DepartmentActivityAssignmentForm
    permission_required = "ministerios.manage_departmentactivityscales"

    def get_activity(self):
        if not hasattr(self, "_activity"):
            self._activity = get_object_or_404(
                DepartmentActivity.objects.select_related("department").prefetch_related(
                    "assignments__member"
                ),
                pk=self.kwargs["pk"],
                department_id=self.kwargs["department_pk"],
            )
        return self._activity

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["activity"] = self.get_activity()
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Pessoa adicionada à escala.")
        return super().form_valid(form)

    def get_success_url(self):
        activity = self.get_activity()
        return reverse(
            "department-activity-scale",
            kwargs={"department_pk": activity.department_id, "pk": activity.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"] = self.get_activity()
        context["department"] = context["activity"].department
        context["assignments"] = context["activity"].assignments.select_related(
            "member"
        )
        return context


class DepartmentActivityAssignmentDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "ministerios.manage_departmentactivityscales"

    def post(self, request, *args, **kwargs):
        activity = get_object_or_404(
            DepartmentActivity,
            pk=kwargs["pk"],
            department_id=kwargs["department_pk"],
        )
        assignment = get_object_or_404(
            DepartmentActivityAssignment,
            pk=kwargs["assignment_pk"],
            activity=activity,
        )
        assignment.delete()
        messages.success(request, "Pessoa removida da escala.")
        return redirect(
            "department-activity-scale",
            department_pk=activity.department_id,
            pk=activity.pk,
        )


class DepartmentAttendanceReportView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = Department
    template_name = "ministerios/attendance_report.html"
    context_object_name = "department"
    permission_required = "ministerios.view_departmentattendance"

    def get_queryset(self):
        return Department.objects.prefetch_related(
            "activities__participants",
            "activities__attendance_records__member",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_rows = []
        for activity in self.object.activities.all():
            participant_ids = {member.pk for member in activity.participants.all()}
            records = list(activity.attendance_records.all())
            total = len(participant_ids | {record.member_id for record in records})
            present = sum(
                record.status == DepartmentActivityAttendance.Status.PRESENT
                for record in records
            )
            absent = sum(
                record.status == DepartmentActivityAttendance.Status.ABSENT
                for record in records
            )
            report_rows.append(
                {
                    "activity": activity,
                    "total": total,
                    "present": present,
                    "absent": absent,
                    "pending": total - present - absent,
                    "rate": round(present * 100 / total) if total else None,
                    "has_participants": bool(total),
                }
            )
        context["report_rows"] = report_rows
        context["present_total"] = sum(row["present"] for row in report_rows)
        context["absent_total"] = sum(row["absent"] for row in report_rows)
        context["pending_total"] = sum(row["pending"] for row in report_rows)
        return context
