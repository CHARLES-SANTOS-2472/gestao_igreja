from django.urls import path

from .views import (
    AssistanceRecordCreateView,
    AssistanceRecordExportView,
    AssistanceRecordListView,
    AssistanceRecordUpdateView,
    AssistedFamilyCreateView,
    AssistedFamilyDetailView,
    AssistedFamilyListView,
    AssistedFamilyUpdateView,
)

urlpatterns = [
    path("familias/", AssistedFamilyListView.as_view(), name="assisted-family-list"),
    path(
        "familias/nova/",
        AssistedFamilyCreateView.as_view(),
        name="assisted-family-create",
    ),
    path(
        "familias/<int:pk>/",
        AssistedFamilyDetailView.as_view(),
        name="assisted-family-detail",
    ),
    path(
        "familias/<int:pk>/editar/",
        AssistedFamilyUpdateView.as_view(),
        name="assisted-family-update",
    ),
    path("ajudas/", AssistanceRecordListView.as_view(), name="assistance-list"),
    path(
        "ajudas/exportar/",
        AssistanceRecordExportView.as_view(),
        name="assistance-export-pdf",
    ),
    path(
        "ajudas/<int:pk>/editar/",
        AssistanceRecordUpdateView.as_view(),
        name="assistance-update",
    ),
    path(
        "familias/<int:family_pk>/ajudas/nova/",
        AssistanceRecordCreateView.as_view(),
        name="assistance-create",
    ),
]
