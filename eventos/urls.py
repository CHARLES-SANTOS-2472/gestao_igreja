from django.urls import path

from .views import (
    AssignmentCreateView,
    AttendanceUpdateView,
    EventCreateView,
    EventDetailView,
    EventListView,
    EventUpdateView,
    ProgramItemCreateView,
    RegistrationCreateView,
    ReservationCreateView,
    ReservationListView,
    ReservationUpdateView,
)

urlpatterns = [
    path("", EventListView.as_view(), name="event-list"),
    path("novo/", EventCreateView.as_view(), name="event-create"),
    path("reservas/", ReservationListView.as_view(), name="reservation-list"),
    path("reservas/nova/", ReservationCreateView.as_view(), name="reservation-create"),
    path(
        "reservas/<int:pk>/editar/",
        ReservationUpdateView.as_view(),
        name="reservation-update",
    ),
    path("<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    path("<int:pk>/editar/", EventUpdateView.as_view(), name="event-update"),
    path(
        "<int:event_pk>/programacao/nova/",
        ProgramItemCreateView.as_view(),
        name="program-item-create",
    ),
    path(
        "<int:event_pk>/escala/nova/",
        AssignmentCreateView.as_view(),
        name="assignment-create",
    ),
    path(
        "<int:event_pk>/inscricoes/nova/",
        RegistrationCreateView.as_view(),
        name="registration-create",
    ),
    path(
        "inscricoes/<int:pk>/presenca/",
        AttendanceUpdateView.as_view(),
        name="attendance-update",
    ),
]
