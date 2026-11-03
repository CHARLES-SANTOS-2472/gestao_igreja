from django.urls import path

from .views import (
    ChurchMessageUpdateView,
    DashboardView,
    MemberCreateView,
    MemberDetailView,
    MemberListView,
    MemberUpdateView,
    OccasionCreateView,
    OccasionListView,
    OccasionUpdateView,
    VisitorCreateView,
    VisitorListView,
    cbo_occupation_search,
    occasion_delete,
    promote_visitor_to_member,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("mensagem/editar/", ChurchMessageUpdateView.as_view(), name="church-message-update"),
    path("ocasioes/", OccasionListView.as_view(), name="occasion-list"),
    path("ocasioes/nova/", OccasionCreateView.as_view(), name="occasion-create"),
    path("ocasioes/<int:pk>/editar/", OccasionUpdateView.as_view(), name="occasion-update"),
    path("ocasioes/<int:pk>/excluir/", occasion_delete, name="occasion-delete"),
    path("pessoas/profissoes/cbo/", cbo_occupation_search, name="cbo-occupation-search"),
    path("visitantes/", VisitorListView.as_view(), name="visitor-list"),
    path("visitantes/novo/", VisitorCreateView.as_view(), name="visitor-create"),
    path(
        "visitantes/<int:pk>/tornar-membro/",
        promote_visitor_to_member,
        name="visitor-promote",
    ),
    path("pessoas/", MemberListView.as_view(), name="member-list"),
    path("pessoas/nova/", MemberCreateView.as_view(), name="member-create"),
    path("pessoas/<int:pk>/", MemberDetailView.as_view(), name="member-detail"),
    path("pessoas/<int:pk>/editar/", MemberUpdateView.as_view(), name="member-update"),
]
