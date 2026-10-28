from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_POST
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from assistencia_social.models import AssistedFamily
from eventos.models import ChurchEvent, SpaceReservation
from financeiro.models import DonationRecord, FinancialTransaction
from ministerios.models import Department
from patrimonio.models import AdministrativeTask, ChurchAsset

from .dashboard_charts import build_charts
from .forms import MemberForm
from .models import CboOccupation, Member


@login_required
@permission_required("membros.view_member", raise_exception=True)
@require_GET
def cbo_occupation_search(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    occupations = CboOccupation.objects.filter(
        Q(code__icontains=query) | Q(title__icontains=query)
    ).order_by("title", "code")[:20]
    return JsonResponse(
        {
            "results": [
                {"code": occupation.code, "title": occupation.title}
                for occupation in occupations
            ]
        }
    )


@login_required
@permission_required("membros.change_member", raise_exception=True)
@require_POST
def promote_visitor_to_member(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if member.status not in (Member.Status.VISITOR, Member.Status.NEW_CONVERT):
        messages.error(
            request,
            "Somente visitantes e novos convertidos podem ser transformados em membros.",
        )
        return redirect("member-detail", pk=member.pk)

    member.status = Member.Status.MEMBER
    if member.joined_on is None:
        member.joined_on = timezone.localdate()
    member.save(update_fields=("status", "joined_on", "updated_at"))
    messages.success(request, "Cadastro atualizado: agora esta pessoa é membro.")
    return redirect("member-detail", pk=member.pk)


class DashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "membros/dashboard.html"
    permission_required = ()

    dashboard_permissions = (
        "membros.view_member",
        "eventos.view_churchevent",
        "eventos.view_spacereservation",
        "ministerios.view_department",
        "financeiro.view_financialtransaction",
        "financeiro.view_donationrecord",
        "patrimonio.view_churchasset",
        "patrimonio.view_administrativetask",
        "assistencia_social.view_assistedfamily",
    )

    def has_permission(self):
        return any(
            self.request.user.has_perm(permission)
            for permission in self.dashboard_permissions
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        cards = []
        upcoming_events = ()

        if user.has_perm("membros.view_member"):
            people = Member.objects.filter(is_placeholder=False)
            cards.extend(
                (
                    {
                        "code": "ME",
                        "title": "Membros e congregados",
                        "count": people.filter(
                            status__in=(
                                Member.Status.MEMBER,
                                Member.Status.CONGREGANT,
                            )
                        ).count(),
                        "description": "Pessoas com vínculo ativo",
                        "url": reverse_lazy("member-list"),
                    },
                    {
                        "code": "VI",
                        "title": "Visitantes",
                        "count": people.filter(
                            status__in=(
                                Member.Status.VISITOR,
                                Member.Status.NEW_CONVERT,
                            )
                        ).count(),
                        "description": "Acompanhamento e novos convertidos",
                        "url": reverse_lazy("visitor-list"),
                    },
                )
            )

        if user.has_perm("eventos.view_churchevent"):
            upcoming_queryset = ChurchEvent.objects.filter(
                status=ChurchEvent.Status.PUBLISHED,
                ends_at__gte=timezone.now(),
            ).order_by("starts_at")
            cards.append(
                {
                    "code": "AG",
                    "title": "Agenda e eventos",
                    "count": upcoming_queryset.count(),
                    "description": "Eventos publicados por vir",
                    "url": reverse_lazy("event-list"),
                }
            )
            upcoming_events = upcoming_queryset[:3]

        if user.has_perm("eventos.view_spacereservation"):
            cards.append(
                {
                    "code": "RE",
                    "title": "Reservas",
                    "count": SpaceReservation.objects.filter(
                        status=SpaceReservation.Status.RESERVED,
                        starts_at__gte=timezone.now(),
                    ).count(),
                    "description": "Reservas futuras confirmadas",
                    "url": reverse_lazy("reservation-list"),
                }
            )

        if user.has_perm("ministerios.view_department"):
            cards.append(
                {
                    "code": "MI",
                    "title": "Ministérios",
                    "count": Department.objects.filter(active=True).count(),
                    "description": "Departamentos em atividade",
                    "url": reverse_lazy("department-list"),
                }
            )

        if user.has_perm("financeiro.view_financialtransaction"):
            cards.append(
                {
                    "code": "FI",
                    "title": "Financeiro",
                    "count": FinancialTransaction.objects.filter(
                        status=FinancialTransaction.Status.PENDING
                    ).count(),
                    "description": "Lançamentos pendentes",
                    "url": reverse_lazy("financial-dashboard"),
                }
            )

        if user.has_perm("financeiro.view_donationrecord"):
            cards.append(
                {
                    "code": "DO",
                    "title": "Doações",
                    "count": DonationRecord.objects.filter(
                        status=DonationRecord.Status.RECEIVED
                    ).count(),
                    "description": "Registros recebidos",
                    "url": reverse_lazy("donation-list"),
                }
            )

        if user.has_perm("patrimonio.view_churchasset"):
            cards.append(
                {
                    "code": "PA",
                    "title": "Patrimônio",
                    "count": ChurchAsset.objects.filter(
                        status=ChurchAsset.Status.ACTIVE
                    ).count(),
                    "description": "Bens em uso",
                    "url": reverse_lazy("asset-list"),
                }
            )

        if user.has_perm("patrimonio.view_administrativetask"):
            cards.append(
                {
                    "code": "TA",
                    "title": "Tarefas",
                    "count": AdministrativeTask.objects.filter(
                        status__in=(
                            AdministrativeTask.Status.OPEN,
                            AdministrativeTask.Status.IN_PROGRESS,
                        )
                    ).count(),
                    "description": "Demandas por acompanhar",
                    "url": reverse_lazy("task-list"),
                }
            )

        if user.has_perm("assistencia_social.view_assistedfamily"):
            cards.append(
                {
                    "code": "AS",
                    "title": "Assistência social",
                    "count": AssistedFamily.objects.filter(active=True).count(),
                    "description": "Famílias em acompanhamento",
                    "url": reverse_lazy("assisted-family-list"),
                }
            )

        context["dashboard_cards"] = cards
        context["charts"] = build_charts(user)
        context["upcoming_events"] = upcoming_events
        return context


class MemberListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Member
    template_name = "membros/member_list.html"
    context_object_name = "members"
    permission_required = "membros.view_member"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Member.objects.select_related("spouse")
            .annotate(child_count=Count("children", distinct=True))
            .order_by("first_name", "last_name")
        )
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        group = self.get_group()
        if group == "members":
            allowed_statuses = (
                Member.Status.MEMBER,
                Member.Status.CONGREGANT,
                Member.Status.TRANSFERRED,
                Member.Status.INACTIVE,
            )
            if status:
                queryset = (
                    queryset.filter(status=status)
                    if status in allowed_statuses
                    else queryset.none()
                )
            else:
                queryset = queryset.filter(status__in=allowed_statuses)
        elif group == "visitors":
            allowed_statuses = (Member.Status.VISITOR, Member.Status.NEW_CONVERT)
            if status:
                queryset = (
                    queryset.filter(status=status)
                    if status in allowed_statuses
                    else queryset.none()
                )
            else:
                queryset = queryset.filter(status__in=allowed_statuses)
        elif status in Member.Status.values:
            queryset = queryset.filter(status=status)
        if group != "all":
            queryset = queryset.filter(is_placeholder=False)
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(cpf__icontains=query)
                | Q(email__icontains=query)
                | Q(mobile__icontains=query)
            )
        return queryset

    def get_group(self):
        group = self.request.GET.get("group", "members").strip()
        return group if group in ("members", "visitors", "all") else "members"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_group()
        if group == "visitors":
            context.update(
                page_title="Visitantes e novos convertidos",
                page_description="Cadastre visitantes e acompanhe novos convertidos.",
                create_label="Novo visitante",
                create_url="visitor-create",
                group_filter="visitors",
                person_label="visitante",
                statuses=(
                    (Member.Status.VISITOR, "Visitante"),
                    (Member.Status.NEW_CONVERT, "Novo convertido"),
                ),
            )
        elif group == "all":
            context.update(
                page_title="Todas as pessoas",
                page_description="Pesquise e gerencie todos os cadastros.",
                create_label="Novo cadastro",
                create_url="member-create",
                group_filter="all",
                person_label="pessoa",
                statuses=Member.Status.choices,
            )
        else:
            context.update(
                page_title="Membros e congregados",
                page_description="Pesquise e gerencie membros, congregados e seus vínculos com a igreja.",
                create_label="Novo membro",
                create_url="member-create",
                group_filter="members",
                person_label="membro",
                statuses=(
                    (Member.Status.MEMBER, "Membro"),
                    (Member.Status.CONGREGANT, "Congregado"),
                    (Member.Status.TRANSFERRED, "Transferido"),
                    (Member.Status.INACTIVE, "Inativo"),
                ),
            )
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_status"] = self.request.GET.get("status", "").strip()
        return context


class VisitorListView(MemberListView):
    def get_group(self):
        return "visitors"


class MemberDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Member
    template_name = "membros/member_detail.html"
    context_object_name = "member"
    permission_required = "membros.view_member"

    def get_queryset(self):
        return Member.objects.select_related("spouse").prefetch_related(
            "spouse_links", "parents", "children"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.object
        context["spouse"] = member.spouse or member.spouse_links.first()
        return context


class MemberCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "membros/member_form.html"
    permission_required = "membros.add_member"
    success_message = "Cadastro realizado com sucesso."

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["person_list_url"] = reverse_lazy("member-list") + "?group=members"
        context["form_section_label"] = "MEMBROS"
        context["form_page_title"] = "Novo membro"
        return context

    def get_success_url(self):
        return reverse_lazy("member-detail", kwargs={"pk": self.object.pk})


class MemberUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "membros/member_form.html"
    permission_required = "membros.change_member"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Cadastro atualizado com sucesso.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_visitor = self.object.status in (
            Member.Status.VISITOR,
            Member.Status.NEW_CONVERT,
        )
        if is_visitor:
            context["person_list_url"] = reverse_lazy("visitor-list")
            context["form_section_label"] = "VISITANTES"
        elif self.object.is_placeholder:
            context["person_list_url"] = (
                reverse_lazy("member-list") + "?group=all&status=pending"
            )
            context["form_section_label"] = "CADASTROS INCOMPLETOS"
        else:
            context["person_list_url"] = (
                reverse_lazy("member-list") + "?group=members"
            )
            context["form_section_label"] = "MEMBROS"
        return context

    def get_success_url(self):
        return reverse_lazy("member-detail", kwargs={"pk": self.object.pk})


class VisitorCreateView(MemberCreateView):
    success_message = "Visitante cadastrado com sucesso."

    def get_initial(self):
        initial = super().get_initial()
        initial["status"] = Member.Status.VISITOR
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["status"].choices = (
            (Member.Status.VISITOR, "Visitante"),
            (Member.Status.NEW_CONVERT, "Novo convertido"),
        )
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["person_list_url"] = reverse_lazy("visitor-list")
        context["form_section_label"] = "VISITANTES"
        context["form_page_title"] = "Novo visitante"
        return context
