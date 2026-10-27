from django.urls import path

from .views import (
    AssetCreateView,
    AssetDetailView,
    AssetListView,
    AssetMaintenanceCreateView,
    AssetUpdateView,
    AdministrativeTaskCreateView,
    AdministrativeTaskDetailView,
    AdministrativeTaskListView,
    AdministrativeTaskUpdateView,
    ContractCreateView,
    ContractListView,
    ContractUpdateView,
    SupplierCreateView,
    SupplierListView,
    SupplierUpdateView,
)

urlpatterns = [
    path("", AssetListView.as_view(), name="asset-list"),
    path("fornecedores/", SupplierListView.as_view(), name="supplier-list"),
    path("fornecedores/novo/", SupplierCreateView.as_view(), name="supplier-create"),
    path(
        "fornecedores/<int:pk>/editar/",
        SupplierUpdateView.as_view(),
        name="supplier-update",
    ),
    path("contratos/", ContractListView.as_view(), name="contract-list"),
    path("contratos/novo/", ContractCreateView.as_view(), name="contract-create"),
    path(
        "contratos/<int:pk>/editar/",
        ContractUpdateView.as_view(),
        name="contract-update",
    ),
    path("tarefas/", AdministrativeTaskListView.as_view(), name="task-list"),
    path("tarefas/nova/", AdministrativeTaskCreateView.as_view(), name="task-create"),
    path(
        "tarefas/<int:pk>/",
        AdministrativeTaskDetailView.as_view(),
        name="task-detail",
    ),
    path(
        "tarefas/<int:pk>/editar/",
        AdministrativeTaskUpdateView.as_view(),
        name="task-update",
    ),
    path("novo/", AssetCreateView.as_view(), name="asset-create"),
    path(
        "<int:asset_pk>/manutencoes/nova/",
        AssetMaintenanceCreateView.as_view(),
        name="asset-maintenance-create",
    ),
    path("<int:pk>/", AssetDetailView.as_view(), name="asset-detail"),
    path("<int:pk>/editar/", AssetUpdateView.as_view(), name="asset-update"),
]
