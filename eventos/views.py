from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import (
    AttendanceForm,
    EventAssignmentForm,
    EventForm,
    EventProgramItemForm,
    EventRegistrationForm,
    SpaceReservationForm,
)
from .models import (
    ChurchEvent,
    EventAssignment,
    EventProgramItem,
    EventRegistration,
    SpaceReservation,
)


class EventListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ChurchEvent
    template_name = "eventos/event_list.html"
    context_object_name = "events"
    permission_required = "eventos.view_churchevent"
    paginate_by = 20

    def get_queryset(self):
        queryset = ChurchEvent.objects.annotate(
            registration_count=Count("registrations", distinct=True)
        ).order_by("starts_at", "title")
        search = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(location__icontains=search)
            )
        if status in ChurchEvent.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        context["statuses"] = ChurchEvent.Status.choices
        return context


class EventCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ChurchEvent
    form_class = EventForm
    template_name = "eventos/event_form.html"
    permission_required = "eventos.add_churchevent"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Evento cadastrado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("event-detail", kwargs={"pk": self.object.pk})


class EventUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ChurchEvent
    form_class = EventForm
    template_name = "eventos/event_form.html"
    permission_required = "eventos.change_churchevent"

    def form_valid(self, form):
        messages.success(self.request, "Evento atualizado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("event-detail", kwargs={"pk": self.object.pk})


class EventDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ChurchEvent
    template_name = "eventos/event_detail.html"
    context_object_name = "event"
    permission_required = "eventos.view_churchevent"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        user = self.request.user
        context["program_items"] = event.program_items.all()
        context["assignments"] = (
            event.assignments.select_related("member").all()
            if user.has_perm("eventos.view_eventassignment")
            else None
        )
        context["registrations"] = (
            event.registrations.select_related("member").all()
            if user.has_perm("eventos.view_eventregistration")
            else None
        )
        context["reservations"] = event.reservations.select_related("space").all()
        context["reservation_count"] = context["reservations"].count()
        context["registration_count"] = event.registrations.count()
        context["attendance_count"] = event.registrations.filter(attended=True).count()
        return context


class EventBoundCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(ChurchEvent, pk=kwargs["event_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.event
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def get_success_url(self):
        return reverse("event-detail", kwargs={"pk": self.event.pk})


class ProgramItemCreateView(EventBoundCreateView):
    model = EventProgramItem
    form_class = EventProgramItemForm
    template_name = "eventos/child_form.html"
    permission_required = "eventos.add_eventprogramitem"
    success_message = "Item adicionado à programação."
    form_title = "Adicionar item à programação"
    back_label = "Voltar ao evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["form_title"] = self.form_title
        context["back_label"] = self.back_label
        return context


class AssignmentCreateView(EventBoundCreateView):
    model = EventAssignment
    form_class = EventAssignmentForm
    template_name = "eventos/child_form.html"
    permission_required = "eventos.add_eventassignment"
    success_message = "Pessoa adicionada à escala."
    form_title = "Adicionar pessoa à escala"
    back_label = "Voltar ao evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["form_title"] = self.form_title
        context["back_label"] = self.back_label
        return context


class RegistrationCreateView(EventBoundCreateView):
    model = EventRegistration
    form_class = EventRegistrationForm
    template_name = "eventos/child_form.html"
    permission_required = "eventos.add_eventregistration"
    success_message = "Inscrição registrada."
    form_title = "Registrar inscrição"
    back_label = "Voltar ao evento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["form_title"] = self.form_title
        context["back_label"] = self.back_label
        return context


class AttendanceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = EventRegistration
    form_class = AttendanceForm
    template_name = "eventos/attendance_form.html"
    permission_required = "eventos.change_eventregistration"

    def get_queryset(self):
        return EventRegistration.objects.select_related("event", "member")

    def get_success_url(self):
        return reverse("event-detail", kwargs={"pk": self.object.event_id})

    def form_valid(self, form):
        messages.success(self.request, "Presença atualizada.")
        return super().form_valid(form)


class ReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SpaceReservation
    template_name = "eventos/reservation_list.html"
    context_object_name = "reservations"
    permission_required = "eventos.view_spacereservation"
    paginate_by = 20

    def get_queryset(self):
        return SpaceReservation.objects.select_related("space", "event").order_by(
            "starts_at"
        )


class ReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SpaceReservation
    form_class = SpaceReservationForm
    template_name = "eventos/reservation_form.html"
    permission_required = "eventos.add_spacereservation"
    success_url = reverse_lazy("reservation-list")

    def get_initial(self):
        initial = super().get_initial()
        event_id = self.request.GET.get("event")
        if event_id:
            initial["event"] = get_object_or_404(
                ChurchEvent.objects.exclude(status=ChurchEvent.Status.CANCELLED),
                pk=event_id,
            )
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Reserva registrada.")
        return super().form_valid(form)


class ReservationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = SpaceReservation
    form_class = SpaceReservationForm
    template_name = "eventos/reservation_form.html"
    permission_required = "eventos.change_spacereservation"
    success_url = reverse_lazy("reservation-list")

    def form_valid(self, form):
        messages.success(self.request, "Reserva atualizada.")
        return super().form_valid(form)
