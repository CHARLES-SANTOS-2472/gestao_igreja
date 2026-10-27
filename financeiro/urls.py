from django.urls import path

from .views import (
    DonationRecordCancelView,
    DonationRecordCreateView,
    DonationRecordDetailView,
    DonationRecordListView,
    FinancialAccountCreateView,
    FinancialAccountDetailView,
    FinancialAccountListView,
    FinancialAccountUpdateView,
    FinancialCategoryCreateView,
    FinancialCategoryListView,
    FinancialCategoryUpdateView,
    FinancialDashboardView,
    FinancialReportView,
    FinancialTransactionCreateView,
    FinancialTransactionDetailView,
    FinancialTransactionListView,
    FinancialTransactionUpdateView,
    PixContributionView,
)

urlpatterns = [
    path("", FinancialDashboardView.as_view(), name="financial-dashboard"),
    path("relatorios/", FinancialReportView.as_view(), name="financial-report"),
    path("pix/", PixContributionView.as_view(), name="financial-pix"),
    path("doacoes/", DonationRecordListView.as_view(), name="donation-list"),
    path("doacoes/nova/", DonationRecordCreateView.as_view(), name="donation-create"),
    path(
        "doacoes/<int:pk>/",
        DonationRecordDetailView.as_view(),
        name="donation-detail",
    ),
    path(
        "doacoes/<int:pk>/cancelar/",
        DonationRecordCancelView.as_view(),
        name="donation-cancel",
    ),
    path("lancamentos/", FinancialTransactionListView.as_view(), name="financial-transaction-list"),
    path(
        "lancamentos/novo/",
        FinancialTransactionCreateView.as_view(),
        name="financial-transaction-create",
    ),
    path(
        "lancamentos/<int:pk>/",
        FinancialTransactionDetailView.as_view(),
        name="financial-transaction-detail",
    ),
    path(
        "lancamentos/<int:pk>/editar/",
        FinancialTransactionUpdateView.as_view(),
        name="financial-transaction-update",
    ),
    path("categorias/", FinancialCategoryListView.as_view(), name="financial-category-list"),
    path(
        "categorias/nova/",
        FinancialCategoryCreateView.as_view(),
        name="financial-category-create",
    ),
    path(
        "categorias/<int:pk>/editar/",
        FinancialCategoryUpdateView.as_view(),
        name="financial-category-update",
    ),
    path("contas/", FinancialAccountListView.as_view(), name="financial-account-list"),
    path(
        "contas/nova/",
        FinancialAccountCreateView.as_view(),
        name="financial-account-create",
    ),
    path(
        "contas/<int:pk>/",
        FinancialAccountDetailView.as_view(),
        name="financial-account-detail",
    ),
    path(
        "contas/<int:pk>/editar/",
        FinancialAccountUpdateView.as_view(),
        name="financial-account-update",
    ),
]
