import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import (
    AdministrativeTaskForm,
    AssetMaintenanceForm,
    ChurchAssetForm,
    ContractForm,
    SupplierForm,
)
from .models import (
    AdministrativeTask,
    AdministrativeTaskAudit,
    AssetMaintenance,
    ChurchAsset,
    Contract,
    Supplier,
)


def administrative_task_snapshot(task):
    return {
        "título": task.title,
        "descrição": task.description,
        "prazo": task.due_date.isoformat() if task.due_date else None,
        "prioridade": task.get_priority_display(),
        "situação": task.get_status_display(),
        "responsável": (
            task.assigned_to.get_full_name() or task.assigned_to.get_username()
            if task.assigned_to
            else None
        ),
    }


class AssetListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ChurchAsset
    template_name = "patrimonio/asset_list.html"
    context_object_name = "assets"
    permission_required = "patrimonio.view_churchasset"
    paginate_by = 25

    def get_queryset(self):
        queryset = ChurchAsset.objects.all()
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(asset_tag__icontains=query)
                | Q(serial_number__icontains=query)
                | Q(location__icontains=query)
            )
        if status in ChurchAsset.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("status", "").strip(),
                "statuses": ChurchAsset.Status.choices,
                "can_add": self.request.user.has_perm("patrimonio.add_churchasset"),
                "can_change": self.request.user.has_perm(
                    "patrimonio.change_churchasset"
                ),
            }
        )
        return context


class AssetCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ChurchAsset
    form_class = ChurchAssetForm
    template_name = "patrimonio/asset_form.html"
    permission_required = "patrimonio.add_churchasset"

    def form_valid(self, form):
        messages.success(self.request, "Bem patrimonial cadastrado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("asset-detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Novo bem patrimonial"
        return context


class AssetUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ChurchAsset
    form_class = ChurchAssetForm
    template_name = "patrimonio/asset_form.html"
    permission_required = "patrimonio.change_churchasset"

    def form_valid(self, form):
        messages.success(self.request, "Bem patrimonial atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("asset-detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Editar bem patrimonial"
        return context


class AssetDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ChurchAsset
    template_name = "patrimonio/asset_detail.html"
    context_object_name = "asset"
    permission_required = "patrimonio.view_churchasset"

    def get_queryset(self):
        return ChurchAsset.objects.prefetch_related(
            "maintenance_records__recorded_by"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_change"] = self.request.user.has_perm(
            "patrimonio.change_churchasset"
        )
        context["can_add_maintenance"] = self.request.user.has_perm(
            "patrimonio.add_assetmaintenance"
        )
        context["can_view_maintenance"] = self.request.user.has_perm(
            "patrimonio.view_assetmaintenance"
        )
        if context["can_view_maintenance"]:
            context["maintenance_records"] = self.object.maintenance_records.all()
            context["upcoming_maintenance"] = self.object.maintenance_records.filter(
                next_maintenance_on__gte=timezone.localdate()
            ).order_by("next_maintenance_on").first()
        return context


class AssetMaintenanceCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = AssetMaintenance
    form_class = AssetMaintenanceForm
    template_name = "patrimonio/maintenance_form.html"
    permission_required = "patrimonio.add_assetmaintenance"

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(ChurchAsset, pk=kwargs["asset_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.asset = self.asset
        form.instance.recorded_by = self.request.user
        messages.success(self.request, "Manutenção registrada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("asset-detail", kwargs={"pk": self.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["asset"] = self.asset
        return context


class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Supplier
    template_name = "patrimonio/supplier_list.html"
    context_object_name = "suppliers"
    permission_required = "patrimonio.view_supplier"
    paginate_by = 25

    def get_queryset(self):
        queryset = Supplier.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(cnpj__icontains=query)
                | Q(contact_name__icontains=query)
                | Q(email__icontains=query)
            )
        active = self.request.GET.get("active", "").strip()
        if active in ("true", "false"):
            queryset = queryset.filter(active=active == "true")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_active": self.request.GET.get("active", "").strip(),
                "can_add": self.request.user.has_perm("patrimonio.add_supplier"),
            }
        )
        return context


class SupplierCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "patrimonio/supplier_form.html"
    permission_required = "patrimonio.add_supplier"

    def form_valid(self, form):
        messages.success(self.request, "Fornecedor cadastrado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("supplier-list")


class SupplierUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "patrimonio/supplier_form.html"
    permission_required = "patrimonio.change_supplier"

    def form_valid(self, form):
        messages.success(self.request, "Fornecedor atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("supplier-list")


class ContractListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Contract
    template_name = "patrimonio/contract_list.html"
    context_object_name = "contracts"
    permission_required = "patrimonio.view_contract"
    paginate_by = 25

    def get_queryset(self):
        queryset = Contract.objects.select_related("supplier")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(contract_number__icontains=query)
                | Q(supplier__name__icontains=query)
            )
        today = timezone.localdate()
        state = self.request.GET.get("state", "").strip()
        if state == "upcoming":
            queryset = queryset.filter(
                status=Contract.Status.ACTIVE,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30),
            )
        elif state == "overdue":
            queryset = queryset.filter(
                status=Contract.Status.ACTIVE, end_date__lt=today
            )
        elif state == "cancelled":
            queryset = queryset.filter(status=Contract.Status.CANCELLED)
        elif state == "active":
            queryset = queryset.filter(
                status=Contract.Status.ACTIVE, end_date__gte=today
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        for contract in context["contracts"]:
            contract.days_remaining = (contract.end_date - today).days
            contract.display_status = contract.get_effective_status(today)
        expiring_contracts = Contract.objects.filter(
            status=Contract.Status.ACTIVE,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=30),
        ).select_related("supplier")
        for contract in expiring_contracts:
            contract.days_remaining = (contract.end_date - today).days
        context.update(
            {
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_state": self.request.GET.get("state", "").strip(),
                "today": today,
                "can_add": self.request.user.has_perm("patrimonio.add_contract"),
                "expiring_contracts": expiring_contracts,
                "overdue_contract_count": Contract.objects.filter(
                    status=Contract.Status.ACTIVE, end_date__lt=today
                ).count(),
            }
        )
        return context


class ContractCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "patrimonio/contract_form.html"
    permission_required = "patrimonio.add_contract"

    def form_valid(self, form):
        messages.success(self.request, "Contrato cadastrado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("contract-list")


class ContractUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "patrimonio/contract_form.html"
    permission_required = "patrimonio.change_contract"

    def form_valid(self, form):
        messages.success(self.request, "Contrato atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("contract-list")


class AdministrativeTaskListView(
    LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    model = AdministrativeTask
    template_name = "patrimonio/task_list.html"
    context_object_name = "tasks"
    permission_required = "patrimonio.view_administrativetask"
    paginate_by = 25

    def get_queryset(self):
        queryset = AdministrativeTask.objects.select_related("assigned_to", "created_by")
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        priority = self.request.GET.get("priority", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(assigned_to__username__icontains=query)
                | Q(assigned_to__first_name__icontains=query)
                | Q(assigned_to__last_name__icontains=query)
            )
        if status in AdministrativeTask.Status.values:
            queryset = queryset.filter(status=status)
        if priority in AdministrativeTask.Priority.values:
            queryset = queryset.filter(priority=priority)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        open_tasks = AdministrativeTask.objects.exclude(
            status__in=(
                AdministrativeTask.Status.COMPLETED,
                AdministrativeTask.Status.CANCELLED,
            )
        )
        due_soon_tasks = open_tasks.filter(
            due_date__gte=today,
            due_date__lte=today + timedelta(days=7),
        ).select_related("assigned_to")[:5]
        my_open_tasks = open_tasks.filter(
            assigned_to=self.request.user
        ).select_related("assigned_to")[:5]
        context.update(
            {
                "today": today,
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_status": self.request.GET.get("status", "").strip(),
                "selected_priority": self.request.GET.get("priority", "").strip(),
                "statuses": AdministrativeTask.Status.choices,
                "priorities": AdministrativeTask.Priority.choices,
                "open_count": open_tasks.count(),
                "overdue_count": open_tasks.filter(due_date__lt=today).count(),
                "due_soon_count": open_tasks.filter(
                    due_date__gte=today,
                    due_date__lte=today + timedelta(days=7),
                ).count(),
                "due_soon_tasks": due_soon_tasks,
                "my_open_tasks": my_open_tasks,
                "can_add": self.request.user.has_perm(
                    "patrimonio.add_administrativetask"
                ),
                "can_change": self.request.user.has_perm(
                    "patrimonio.change_administrativetask"
                ),
            }
        )
        for task in context["tasks"]:
            task.is_overdue = (
                task.due_date is not None
                and task.due_date < today
                and task.status
                not in (
                    AdministrativeTask.Status.COMPLETED,
                    AdministrativeTask.Status.CANCELLED,
                )
            )
        return context


class AdministrativeTaskCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = AdministrativeTask
    form_class = AdministrativeTaskForm
    template_name = "patrimonio/task_form.html"
    permission_required = "patrimonio.add_administrativetask"

    @transaction.atomic
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        self.object = form.save()
        AdministrativeTaskAudit.objects.create(
            task=self.object,
            task_title=self.object.title,
            action=AdministrativeTaskAudit.Action.CREATED,
            after_data=administrative_task_snapshot(self.object),
            actor=self.request.user,
        )
        messages.success(self.request, "Tarefa administrativa cadastrada.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("task-detail", kwargs={"pk": self.object.pk})


class AdministrativeTaskUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = AdministrativeTask
    form_class = AdministrativeTaskForm
    template_name = "patrimonio/task_form.html"
    permission_required = "patrimonio.change_administrativetask"

    @transaction.atomic
    def form_valid(self, form):
        before_data = administrative_task_snapshot(self.get_object())
        self.object = form.save()
        AdministrativeTaskAudit.objects.create(
            task=self.object,
            task_title=self.object.title,
            action=AdministrativeTaskAudit.Action.UPDATED,
            before_data=before_data,
            after_data=administrative_task_snapshot(self.object),
            actor=self.request.user,
        )
        messages.success(self.request, "Tarefa administrativa atualizada.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("task-detail", kwargs={"pk": self.object.pk})


class AdministrativeTaskDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = AdministrativeTask
    template_name = "patrimonio/task_detail.html"
    context_object_name = "task"
    permission_required = "patrimonio.view_administrativetask"

    def get_queryset(self):
        return AdministrativeTask.objects.select_related(
            "assigned_to", "created_by"
        ).prefetch_related("audit_entries__actor")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        for audit in self.object.audit_entries.all():
            audit.before_json = (
                json.dumps(audit.before_data, ensure_ascii=False, indent=2)
                if audit.before_data
                else ""
            )
            audit.after_json = json.dumps(
                audit.after_data, ensure_ascii=False, indent=2
            )
        context["can_change"] = self.request.user.has_perm(
            "patrimonio.change_administrativetask"
        )
        context["is_overdue"] = (
            self.object.due_date is not None
            and self.object.due_date < today
            and self.object.status
            not in (
                AdministrativeTask.Status.COMPLETED,
                AdministrativeTask.Status.CANCELLED,
            )
        )
        return context
