from django.contrib import admin

from .forms import DepartmentForm
from .models import (
    Department,
    DepartmentActivity,
    DepartmentActivityAssignment,
    DepartmentActivityAttendance,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    form = DepartmentForm
    list_display = ("name", "leader", "vice_leader", "active", "member_count")
    list_filter = ("active",)
    search_fields = (
        "name",
        "leader__first_name",
        "leader__last_name",
        "vice_leader__first_name",
        "vice_leader__last_name",
        "members__first_name",
    )

    @admin.display(description="membros")
    def member_count(self, department):
        return department.members.count()


@admin.register(DepartmentActivity)
class DepartmentActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "kind", "starts_at", "status", "responsible")
    list_filter = ("department", "kind", "status")
    search_fields = ("title", "department__name", "responsible__first_name", "responsible__last_name")
    filter_horizontal = ("participants",)


@admin.register(DepartmentActivityAttendance)
class DepartmentActivityAttendanceAdmin(admin.ModelAdmin):
    list_display = ("activity", "member", "status", "updated_at")
    list_filter = ("status", "activity__department")
    search_fields = (
        "activity__title",
        "member__first_name",
        "member__last_name",
    )


@admin.register(DepartmentActivityAssignment)
class DepartmentActivityAssignmentAdmin(admin.ModelAdmin):
    list_display = ("activity", "member", "role", "custom_role")
    list_filter = ("role", "activity__department")
    search_fields = (
        "activity__title",
        "member__first_name",
        "member__last_name",
        "custom_role",
    )
