from django.urls import path

from .views import (
    DashboardView,
    MemberCreateView,
    MemberDetailView,
    MemberListView,
    MemberUpdateView,
    VisitorCreateView,
    VisitorListView,
    cbo_occupation_search,
    promote_visitor_to_member,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
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
