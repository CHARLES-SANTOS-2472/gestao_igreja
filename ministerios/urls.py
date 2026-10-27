from django.urls import path

from .views import (
    DepartmentActivityAssignmentDeleteView,
    DepartmentActivityCreateView,
    DepartmentActivityDetailView,
    DepartmentActivityAttendanceView,
    DepartmentActivityScaleView,
    DepartmentActivityUpdateView,
    DepartmentAttendanceReportView,
    DepartmentCreateView,
    DepartmentDetailView,
    DepartmentListView,
    DepartmentUpdateView,
)

urlpatterns = [
    path("", DepartmentListView.as_view(), name="department-list"),
    path("novo/", DepartmentCreateView.as_view(), name="department-create"),
    path(
        "<int:department_pk>/atividades/nova/",
        DepartmentActivityCreateView.as_view(),
        name="department-activity-create",
    ),
    path(
        "<int:department_pk>/atividades/<int:pk>/",
        DepartmentActivityDetailView.as_view(),
        name="department-activity-detail",
    ),
    path(
        "<int:department_pk>/atividades/<int:pk>/editar/",
        DepartmentActivityUpdateView.as_view(),
        name="department-activity-update",
    ),
    path(
        "<int:department_pk>/atividades/<int:pk>/presencas/",
        DepartmentActivityAttendanceView.as_view(),
        name="department-activity-attendance",
    ),
    path(
        "<int:department_pk>/atividades/<int:pk>/escala/",
        DepartmentActivityScaleView.as_view(),
        name="department-activity-scale",
    ),
    path(
        "<int:department_pk>/atividades/<int:pk>/escala/<int:assignment_pk>/remover/",
        DepartmentActivityAssignmentDeleteView.as_view(),
        name="department-activity-assignment-delete",
    ),
    path(
        "<int:pk>/relatorio-presencas/",
        DepartmentAttendanceReportView.as_view(),
        name="department-attendance-report",
    ),
    path("<int:pk>/", DepartmentDetailView.as_view(), name="department-detail"),
    path("<int:pk>/editar/", DepartmentUpdateView.as_view(), name="department-update"),
]
