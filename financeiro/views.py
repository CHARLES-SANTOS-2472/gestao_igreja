import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    DonationCancellationForm,
    DonationRecordForm,
    FinancialAccountForm,
    FinancialCategoryForm,
    FinancialReportFilterForm,
    FinancialTransactionFilterForm,
    FinancialTransactionForm,
)
from .pix import build_pix_payload, qr_svg
from .models import (
    DonationRecord,
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransactionAudit,
)


def transaction_snapshot(entry):
    return {
        "tipo": entry.get_kind_display(),
        "descrição": entry.title,
        "categoria": str(entry.category),
        "valor": str(entry.amount),
        "data_prevista": entry.due_on.isoformat(),
        "situação": entry.get_status_display(),
        "forma_pagamento": entry.get_payment_method_display()
        if entry.payment_method
        else "Não informada",
        "data_quitacao": entry.settled_on.isoformat() if entry.settled_on else None,
        "conta": str(entry.account) if entry.account else None,
        "departamento": str(entry.department) if entry.department else None,
        "evento": str(entry.event) if entry.event else None,
        "observações": entry.notes,
    }


class PixContributionView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "financeiro/pix.html"
    permission_required = "financeiro.view_financialtransaction"

    PURPOSES = {
        "dizimo": ("Dízimo", "Dízimos", "DIZIMO"),
        "oferta": ("Oferta", "Ofertas", "OFERTA"),
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        purpose = self.request.GET.get("tipo", "dizimo")
        if purpose not in self.PURPOSES:
            purpose = "dizimo"
        label, category_name, reference = self.PURPOSES[purpose]
        amount = None
        raw_amount = self.request.GET.get("valor", "").replace(",", ".").strip()
        if raw_amount:
            try:
                amount = Decimal(raw_amount).quantize(Decimal("0.01"))
                if amount <= 0 or amount > Decimal("99999999.99"):
                    amount = None
            except ArithmeticError:
                amount = None
        payload = build_pix_payload(
            settings.PIX_KEY,
            settings.PIX_RECEIVER_NAME,
            settings.PIX_CITY,
            amount=amount,
            reference=reference,
        )
        context.update(
            purpose=purpose,
            purpose_label=label,
            amount=amount,
            payload=payload,
            qr_svg=mark_safe(qr_svg(payload)),
            category=FinancialCategory.objects.filter(
                name=category_name, kind=FinancialCategory.Kind.INCOME
            ).first(),
            can_add_transaction=self.request.user.has_perm(
                "financeiro.add_financialtransaction"
            ),
        )
        return context


class FinancialDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "financeiro/dashboard.html"
    permission_required = "financeiro.view_financialtransaction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        period_start = today.replace(day=1)
        settled = FinancialTransaction.objects.filter(
            status=FinancialTransaction.Status.SETTLED,
            settled_on__gte=period_start,
            settled_on__lte=today,
        )
        current_month_end = date(
            today.year + (today.month == 12), today.month % 12 + 1, 1
        )
        pending = FinancialTransaction.objects.filter(
            status=FinancialTransaction.Status.PENDING,
            due_on__gte=period_start,
            due_on__lt=current_month_end,
        )
        settled_totals = settled.aggregate(
            income=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)
            ),
            expense=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)
            ),
        )
        pending_totals = pending.aggregate(
            income=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)
            ),
            expense=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)
            ),
        )
        context.update(
            {
                "today": today,
                "month_income": settled_totals["income"] or Decimal("0.00"),
                "month_expense": settled_totals["expense"] or Decimal("0.00"),
                "month_net": (settled_totals["income"] or Decimal("0.00"))
                - (settled_totals["expense"] or Decimal("0.00")),
                "pending_income": pending_totals["income"] or Decimal("0.00"),
                "pending_expense": pending_totals["expense"] or Decimal("0.00"),
                "recent_transactions": FinancialTransaction.objects.select_related(
                    "category", "account"
                )[:8],
                "can_add_transaction": self.request.user.has_perm(
                    "financeiro.add_financialtransaction"
                ),
                "can_view_donations": self.request.user.has_perm(
                    "financeiro.view_donationrecord"
                ),
                "can_add_donation": self.request.user.has_perm(
                    "financeiro.view_donationrecord"
                )
                and self.request.user.has_perm("financeiro.add_donationrecord"),
                "can_manage_categories": self.request.user.has_perm(
                    "financeiro.add_financialcategory"
                )
                or self.request.user.has_perm(
                    "financeiro.change_financialcategory"
                ),
                "can_manage_accounts": self.request.user.has_perm(
                    "financeiro.add_financialaccount"
                )
                or self.request.user.has_perm(
                    "financeiro.change_financialaccount"
                ),
            }
        )
        context["can_manage_categories"] = context["can_manage_categories"] and (
            self.request.user.has_perm("financeiro.view_financialcategory")
        )
        account_balances = []
        can_view_accounts = self.request.user.has_perm(
            "financeiro.view_financialaccount"
        )
        context["can_view_accounts"] = can_view_accounts
        context["can_manage_accounts"] = (
            context["can_manage_accounts"] and can_view_accounts
        )
        if can_view_accounts:
            totals_by_account = {
                totals["account_id"]: totals
                for totals in FinancialTransaction.objects.filter(
                    status=FinancialTransaction.Status.SETTLED,
                    account__active=True,
                )
                .values("account_id")
                .annotate(
                    income=Sum(
                        "amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)
                    ),
                    expense=Sum(
                        "amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)
                    ),
                )
            }
            for account in FinancialAccount.objects.filter(active=True):
                totals = totals_by_account.get(account.pk, {})
                income = totals.get("income") or Decimal("0.00")
                expense = totals.get("expense") or Decimal("0.00")
                account_balances.append(
                    {
                        "account": account,
                        "balance": account.opening_balance + income - expense,
                    }
                )
        if can_view_accounts:
            context["account_balances"] = account_balances
        return context


class FinancialTransactionListView(
    LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    model = FinancialTransaction
    template_name = "financeiro/transaction_list.html"
    context_object_name = "transactions"
    permission_required = "financeiro.view_financialtransaction"
    paginate_by = 25

    def get_queryset(self):
        queryset = FinancialTransaction.objects.select_related(
            "category", "account", "department", "event"
        )
        self.filter_form = FinancialTransactionFilterForm(self.request.GET)
        if not self.filter_form.is_valid():
            return queryset.none()
        filters = self.filter_form.cleaned_data
        search = filters["q"].strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(category__name__icontains=search)
                | Q(department__name__icontains=search)
                | Q(event__title__icontains=search)
            )
        if filters["kind"]:
            queryset = queryset.filter(kind=filters["kind"])
        if filters["status"]:
            queryset = queryset.filter(status=filters["status"])
        if filters["category"]:
            queryset = queryset.filter(category=filters["category"])
        if filters["date_from"]:
            queryset = queryset.filter(due_on__gte=filters["date_from"])
        if filters["date_to"]:
            queryset = queryset.filter(due_on__lte=filters["date_to"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = getattr(
            self,
            "filter_form",
            FinancialTransactionFilterForm(self.request.GET),
        )
        if not filter_form.is_bound:
            filter_form.is_valid()
        context.update(
            {
                "filter_form": filter_form,
                "can_add_transaction": self.request.user.has_perm(
                    "financeiro.add_financialtransaction"
                ),
                "can_change_transaction": self.request.user.has_perm(
                    "financeiro.change_financialtransaction"
                ),
            }
        )
        return context


class FinancialTransactionCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    form_class = FinancialTransactionForm
    template_name = "financeiro/transaction_form.html"
    permission_required = "financeiro.add_financialtransaction"

    def get_initial(self):
        initial = super().get_initial()
        category = FinancialCategory.objects.filter(
            pk=self.request.GET.get("categoria", "").strip() or 0,
            kind=FinancialCategory.Kind.INCOME,
        ).first()
        if category:
            initial.update(
                kind=FinancialTransaction.Kind.INCOME,
                category=category,
                payment_method=FinancialTransaction.PaymentMethod.PIX,
            )
            title = self.request.GET.get("titulo", "").strip()[:150]
            if title:
                initial["title"] = title
        return initial

    @transaction.atomic
    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.updated_by = self.request.user
        self.object.save()
        form.save_m2m()
        FinancialTransactionAudit.objects.create(
            transaction=self.object,
            transaction_label=self.object.title,
            action=FinancialTransactionAudit.Action.CREATED,
            after_data=transaction_snapshot(self.object),
            actor=self.request.user,
        )
        messages.success(self.request, "Lançamento financeiro cadastrado.")
        return redirect("financial-transaction-detail", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Novo lançamento financeiro"
        return context


class FinancialTransactionUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = FinancialTransaction
    form_class = FinancialTransactionForm
    template_name = "financeiro/transaction_form.html"
    permission_required = "financeiro.change_financialtransaction"

    def get_queryset(self):
        return FinancialTransaction.objects.exclude(donation_record__isnull=False)

    @transaction.atomic
    def form_valid(self, form):
        before_data = transaction_snapshot(self.get_object())
        self.object = form.save(commit=False)
        self.object.updated_by = self.request.user
        self.object.save()
        form.save_m2m()
        FinancialTransactionAudit.objects.create(
            transaction=self.object,
            transaction_label=self.object.title,
            action=FinancialTransactionAudit.Action.UPDATED,
            before_data=before_data,
            after_data=transaction_snapshot(self.object),
            actor=self.request.user,
        )
        messages.success(self.request, "Lançamento financeiro atualizado.")
        return redirect("financial-transaction-detail", pk=self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Editar lançamento financeiro"
        return context


class FinancialTransactionDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = FinancialTransaction
    template_name = "financeiro/transaction_detail.html"
    context_object_name = "entry"
    permission_required = "financeiro.view_financialtransaction"

    def get_queryset(self):
        return FinancialTransaction.objects.select_related(
            "category", "account", "department", "event", "created_by", "updated_by"
        ).prefetch_related("audit_entries__actor")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for audit in self.object.audit_entries.all():
            audit.before_json = (
                json.dumps(audit.before_data, ensure_ascii=False, indent=2)
                if audit.before_data
                else ""
            )
            audit.after_json = json.dumps(
                audit.after_data, ensure_ascii=False, indent=2
            )
        context["is_donation_entry"] = DonationRecord.objects.filter(
            financial_transaction=self.object
        ).exists()
        context["can_view_donation_entry"] = self.request.user.has_perm(
            "financeiro.view_donationrecord"
        )
        context["can_change_transaction"] = self.request.user.has_perm(
            "financeiro.change_financialtransaction"
        ) and not context["is_donation_entry"]
        return context


class DonationRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DonationRecord
    template_name = "financeiro/donation_list.html"
    context_object_name = "donations"
    permission_required = "financeiro.view_donationrecord"
    paginate_by = 25

    def get_queryset(self):
        return DonationRecord.objects.select_related(
            "department", "event", "financial_transaction", "recorded_by"
        )


class DonationRecordCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = DonationRecord
    form_class = DonationRecordForm
    template_name = "financeiro/donation_form.html"
    permission_required = (
        "financeiro.view_donationrecord",
        "financeiro.add_donationrecord",
    )

    def has_permission(self):
        if not super().has_permission():
            return False
        donation_type = (
            self.request.POST.get("donation_type", "")
            if self.request.method == "POST"
            else self.request.GET.get("donation_type", "")
        )
        if donation_type == DonationRecord.DonationType.MONEY:
            return self.request.user.has_perms(
                (
                    "financeiro.add_financialtransaction",
                    "financeiro.view_financialaccount",
                )
            )
        return True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["can_view_accounts"] = self.request.user.has_perm(
            "financeiro.view_financialaccount"
        )
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        donation = form.save(commit=False)
        category = None
        if donation.donation_type == DonationRecord.DonationType.MONEY:
            category = FinancialCategory.objects.filter(
                kind=FinancialCategory.Kind.INCOME,
                name="Doações",
                active=True,
            ).first()
            if category is None:
                form.add_error(
                    None,
                    "A categoria financeira ativa “Doações” não está disponível. "
                    "Peça ao administrador para cadastrá-la ou reativá-la.",
                )
                return self.form_invalid(form)
        donation.recorded_by = self.request.user
        donation.save()
        form.save_m2m()
        if donation.donation_type == DonationRecord.DonationType.MONEY:
            destination_label = donation.get_destination_display()
            if donation.department:
                destination_label = str(donation.department)
            elif donation.event:
                destination_label = str(donation.event)
            elif donation.destination_description:
                destination_label = donation.destination_description
            financial_entry = FinancialTransaction.objects.create(
                kind=FinancialTransaction.Kind.INCOME,
                title="Doação recebida",
                category=category,
                amount=donation.amount,
                due_on=donation.received_on,
                status=FinancialTransaction.Status.SETTLED,
                payment_method=form.cleaned_data.get("payment_method", ""),
                settled_on=donation.received_on,
                account=form.cleaned_data["account"],
                department=donation.department,
                event=donation.event,
                notes=f"Doação #{donation.pk} · Destinação: {destination_label}",
                created_by=self.request.user,
                updated_by=self.request.user,
            )
            FinancialTransactionAudit.objects.create(
                transaction=financial_entry,
                transaction_label=financial_entry.title,
                action=FinancialTransactionAudit.Action.CREATED,
                after_data=transaction_snapshot(financial_entry),
                actor=self.request.user,
            )
            donation.financial_transaction = financial_entry
            donation.save(update_fields=["financial_transaction"])
        messages.success(self.request, "Doação registrada.")
        return redirect("donation-detail", pk=donation.pk)


class DonationRecordDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = DonationRecord
    template_name = "financeiro/donation_detail.html"
    context_object_name = "donation"
    permission_required = "financeiro.view_donationrecord"

    def get_queryset(self):
        return DonationRecord.objects.select_related(
            "department",
            "event",
            "financial_transaction__account",
            "recorded_by",
            "cancelled_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancellation_form"] = DonationCancellationForm()
        context["can_cancel"] = (
            self.object.status == DonationRecord.Status.RECEIVED
            and self.request.user.has_perm("financeiro.change_donationrecord")
            and (
                not self.object.financial_transaction_id
                or self.request.user.has_perm(
                    "financeiro.change_financialtransaction"
                )
            )
        )
        return context


class DonationRecordCancelView(
    LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = "financeiro.change_donationrecord"

    @transaction.atomic
    def post(self, request, pk):
        donation = get_object_or_404(
            DonationRecord.objects.select_related("financial_transaction"), pk=pk
        )
        if donation.financial_transaction_id and not request.user.has_perm(
            "financeiro.change_financialtransaction"
        ):
            return self.handle_no_permission()
        if donation.status != DonationRecord.Status.RECEIVED:
            messages.error(request, "Esta doação já foi cancelada.")
            return redirect("donation-detail", pk=donation.pk)
        form = DonationCancellationForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe o motivo para cancelar a doação.")
            return redirect("donation-detail", pk=donation.pk)

        donation.status = DonationRecord.Status.CANCELLED
        donation.cancellation_reason = form.cleaned_data["reason"]
        donation.cancelled_by = request.user
        donation.cancelled_at = timezone.now()
        donation.save(
            update_fields=(
                "status",
                "cancellation_reason",
                "cancelled_by",
                "cancelled_at",
            )
        )
        if donation.financial_transaction_id:
            entry = donation.financial_transaction
            before_data = transaction_snapshot(entry)
            entry.status = FinancialTransaction.Status.CANCELLED
            entry.account = None
            entry.settled_on = None
            entry.updated_by = request.user
            entry.save(
                update_fields=(
                    "status",
                    "account",
                    "settled_on",
                    "updated_by",
                    "updated_at",
                )
            )
            FinancialTransactionAudit.objects.create(
                transaction=entry,
                transaction_label=entry.title,
                action=FinancialTransactionAudit.Action.UPDATED,
                before_data=before_data,
                after_data=transaction_snapshot(entry),
                actor=request.user,
            )
        messages.success(request, "Doação cancelada e receita vinculada atualizada.")
        return redirect("donation-detail", pk=donation.pk)


class FinancialReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "financeiro/report.html"
    permission_required = "financeiro.view_financialtransaction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        if self.request.GET:
            filter_form = FinancialReportFilterForm(self.request.GET)
            valid = filter_form.is_valid()
            if valid:
                date_from = filter_form.cleaned_data["date_from"]
                date_to = filter_form.cleaned_data["date_to"]
            else:
                date_from = date_to = None
        else:
            date_from = today.replace(day=1)
            date_to = today
            filter_form = FinancialReportFilterForm(
                initial={"date_from": date_from, "date_to": date_to}
            )
        if date_from is None:
            date_from = today.replace(day=1)
        if date_to is None:
            date_to = today

        settled = FinancialTransaction.objects.filter(
            status=FinancialTransaction.Status.SETTLED,
            settled_on__gte=date_from,
            settled_on__lte=date_to,
        )
        totals = settled.aggregate(
            income=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)
            ),
            expense=Sum(
                "amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)
            ),
        )
        group_rows = settled.values(
            "kind", "category__name"
        ).annotate(total=Sum("amount"), count=Count("pk")).order_by(
            "kind", "category__name"
        )
        payment_method_rows = settled.values("payment_method").annotate(
            total=Sum("amount"), count=Count("pk")
        ).order_by("payment_method")
        payment_method_labels = dict(FinancialTransaction.PaymentMethod.choices)
        for row in payment_method_rows:
            row["method_label"] = payment_method_labels.get(
                row["payment_method"], "Não informada"
            )
        currency_field = DecimalField(max_digits=12, decimal_places=2)
        department_rows = settled.values("department__name").annotate(
            income=Coalesce(
                Sum("amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)),
                Value(Decimal("0.00")),
                output_field=currency_field,
            ),
            expense=Coalesce(
                Sum("amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)),
                Value(Decimal("0.00")),
                output_field=currency_field,
            ),
        ).annotate(
            net=ExpressionWrapper(
                F("income") - F("expense"),
                output_field=currency_field,
            )
        ).order_by("department__name")
        event_rows = settled.values(
            "event__title"
        ).annotate(
            income=Coalesce(
                Sum("amount", filter=Q(kind=FinancialTransaction.Kind.INCOME)),
                Value(Decimal("0.00")),
                output_field=currency_field,
            ),
            expense=Coalesce(
                Sum("amount", filter=Q(kind=FinancialTransaction.Kind.EXPENSE)),
                Value(Decimal("0.00")),
                output_field=currency_field,
            ),
        ).order_by("event__title")
        context.update(
            {
                "filter_form": filter_form,
                "date_from": date_from,
                "date_to": date_to,
                "income_total": totals["income"] or Decimal("0.00"),
                "expense_total": totals["expense"] or Decimal("0.00"),
                "net_total": (totals["income"] or Decimal("0.00"))
                - (totals["expense"] or Decimal("0.00")),
                "category_rows": group_rows,
                "payment_method_rows": payment_method_rows,
                "department_rows": department_rows,
                "event_rows": event_rows,
                "pending_transactions": FinancialTransaction.objects.filter(
                    status=FinancialTransaction.Status.PENDING,
                    due_on__gte=date_from,
                    due_on__lte=date_to,
                ).select_related("category", "department", "event"),
            }
        )
        return context


class FinancialCategoryListView(
    LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    model = FinancialCategory
    template_name = "financeiro/category_list.html"
    context_object_name = "categories"
    permission_required = "financeiro.view_financialcategory"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_add"] = self.request.user.has_perm(
            "financeiro.add_financialcategory"
        )
        context["can_change"] = self.request.user.has_perm(
            "financeiro.change_financialcategory"
        )
        return context


class FinancialCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = FinancialCategory
    form_class = FinancialCategoryForm
    template_name = "financeiro/setup_form.html"
    permission_required = "financeiro.add_financialcategory"
    extra_context = {"form_title": "Nova categoria financeira"}
    success_url = reverse_lazy("financial-category-list")

    def form_valid(self, form):
        messages.success(self.request, "Categoria financeira cadastrada.")
        return super().form_valid(form)


class FinancialCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = FinancialCategory
    form_class = FinancialCategoryForm
    template_name = "financeiro/setup_form.html"
    permission_required = "financeiro.change_financialcategory"
    extra_context = {"form_title": "Editar categoria financeira"}
    success_url = reverse_lazy("financial-category-list")

    def form_valid(self, form):
        messages.success(self.request, "Categoria financeira atualizada.")
        return super().form_valid(form)


class FinancialAccountListView(
    LoginRequiredMixin, PermissionRequiredMixin, ListView
):
    model = FinancialAccount
    template_name = "financeiro/account_list.html"
    context_object_name = "accounts"
    permission_required = "financeiro.view_financialaccount"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_add"] = self.request.user.has_perm(
            "financeiro.add_financialaccount"
        )
        context["can_change"] = self.request.user.has_perm(
            "financeiro.change_financialaccount"
        )
        return context


class FinancialAccountDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = FinancialAccount
    template_name = "financeiro/account_detail.html"
    context_object_name = "account"
    permission_required = "financeiro.view_financialaccount"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_change"] = self.request.user.has_perm(
            "financeiro.change_financialaccount"
        )
        return context


class FinancialAccountCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = FinancialAccount
    form_class = FinancialAccountForm
    template_name = "financeiro/account_form.html"
    permission_required = "financeiro.add_financialaccount"
    extra_context = {"form_title": "Nova conta financeira"}
    success_url = reverse_lazy("financial-account-list")

    def form_valid(self, form):
        messages.success(self.request, "Conta financeira cadastrada.")
        return super().form_valid(form)


class FinancialAccountUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = FinancialAccount
    form_class = FinancialAccountForm
    template_name = "financeiro/account_form.html"
    permission_required = "financeiro.change_financialaccount"
    extra_context = {"form_title": "Editar conta financeira"}
    success_url = reverse_lazy("financial-account-list")

    def form_valid(self, form):
        messages.success(self.request, "Conta financeira atualizada.")
        return super().form_valid(form)
