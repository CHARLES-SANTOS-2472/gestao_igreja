from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from eventos.models import ChurchEvent
from ministerios.models import Department

from .models import (
    DonationRecord,
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransactionAudit,
)


class FinancialManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tesouraria")
        permissions = Permission.objects.filter(
            content_type__app_label="financeiro",
            codename__in=(
                "view_financialtransaction",
                "add_financialtransaction",
                "change_financialtransaction",
                "view_financialcategory",
                "add_financialcategory",
                "change_financialcategory",
                "view_financialaccount",
                "add_financialaccount",
                "change_financialaccount",
                "view_donationrecord",
                "add_donationrecord",
                "change_donationrecord",
            ),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)
        self.income_category = FinancialCategory.objects.get(
            kind=FinancialCategory.Kind.INCOME,
            name="Dízimos",
        )
        self.offering_category = FinancialCategory.objects.get(
            kind=FinancialCategory.Kind.INCOME,
            name="Ofertas",
        )
        self.expense_category = FinancialCategory.objects.get(
            kind=FinancialCategory.Kind.EXPENSE,
            name="Manutenção",
        )
        self.account = FinancialAccount.objects.create(
            name="Conta principal",
            kind=FinancialAccount.Kind.BANK,
            opening_balance=Decimal("100.00"),
        )
        self.today = timezone.localdate()

    def transaction_data(self, **overrides):
        data = {
            "kind": FinancialTransaction.Kind.INCOME,
            "title": "Dízimo",
            "category": self.income_category.pk,
            "amount": "250.00",
            "due_on": self.today.isoformat(),
            "status": FinancialTransaction.Status.PENDING,
            "settled_on": "",
            "account": "",
            "department": "",
            "event": "",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_finance_pages_require_financial_permissions(self):
        user = get_user_model().objects.create_user(username="sem_financeiro")
        self.client.force_login(user)

        dashboard = self.client.get(reverse("financial-dashboard"))
        transaction_list = self.client.get(reverse("financial-transaction-list"))
        create = self.client.get(reverse("financial-transaction-create"))

        self.assertEqual(dashboard.status_code, 403)
        self.assertEqual(transaction_list.status_code, 403)
        self.assertEqual(create.status_code, 403)

    def test_cash_donation_creates_one_linked_income_and_audit_record(self):
        response = self.client.post(
            reverse("donation-create"),
            {
                "donor_name": "Doador Exemplo",
                "anonymous": "",
                "received_on": self.today.isoformat(),
                "donation_type": DonationRecord.DonationType.MONEY,
                "description": "",
                "amount": "250.00",
                "quantity": "",
                "unit": "",
                "destination": DonationRecord.Destination.GENERAL,
                "department": "",
                "event": "",
                "destination_description": "",
                "account": str(self.account.pk),
                "payment_method": FinancialTransaction.PaymentMethod.PIX,
            },
        )

        self.assertEqual(response.status_code, 302)
        donation = DonationRecord.objects.get(donor_name="Doador Exemplo")
        entry = donation.financial_transaction
        self.assertEqual(entry.kind, FinancialTransaction.Kind.INCOME)
        self.assertEqual(entry.category.name, "Doações")
        self.assertEqual(entry.amount, Decimal("250.00"))
        self.assertEqual(entry.account, self.account)
        self.assertEqual(entry.status, FinancialTransaction.Status.SETTLED)
        self.assertEqual(entry.created_by, self.user)
        self.assertNotIn("Doador Exemplo", entry.title)
        self.assertNotIn("Doador Exemplo", entry.notes)
        self.assertEqual(
            FinancialTransaction.objects.filter(category__name="Doações").count(),
            1,
        )
        self.assertEqual(entry.audit_entries.count(), 1)

    def test_donation_income_cannot_be_manually_added_as_a_second_transaction(self):
        donations_category = FinancialCategory.objects.get(
            kind=FinancialCategory.Kind.INCOME,
            name="Doações",
        )
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(
                title="Doação",
                category=donations_category.pk,
                status=FinancialTransaction.Status.PENDING,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.assertFalse(
            FinancialTransaction.objects.filter(category=donations_category).exists()
        )

    def test_anonymous_goods_donation_records_quantity_without_financial_income(self):
        response = self.client.post(
            reverse("donation-create"),
            {
                "donor_name": "Nome que não deve ser guardado",
                "anonymous": "on",
                "received_on": self.today.isoformat(),
                "donation_type": DonationRecord.DonationType.GOODS,
                "description": "Arroz",
                "amount": "",
                "quantity": "2.5",
                "unit": "kg",
                "destination": DonationRecord.Destination.SOCIAL_ASSISTANCE,
                "department": "",
                "event": "",
                "destination_description": "",
                "account": "",
                "payment_method": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        donation = DonationRecord.objects.get()
        self.assertTrue(donation.anonymous)
        self.assertEqual(donation.donor_name, "")
        self.assertEqual(donation.quantity, Decimal("2.50"))
        self.assertIsNone(donation.financial_transaction)
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_money_donation_requires_account_and_valid_destination(self):
        response = self.client.post(
            reverse("donation-create"),
            {
                "donor_name": "",
                "anonymous": "on",
                "received_on": self.today.isoformat(),
                "donation_type": DonationRecord.DonationType.MONEY,
                "description": "",
                "amount": "75.00",
                "quantity": "",
                "unit": "",
                "destination": DonationRecord.Destination.GENERAL,
                "department": "",
                "event": "",
                "destination_description": "",
                "account": "",
                "payment_method": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("account", response.context["form"].errors)
        self.assertFalse(DonationRecord.objects.exists())
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_cancelling_cash_donation_cancels_its_linked_income_and_audits_it(self):
        create_response = self.client.post(
            reverse("donation-create"),
            {
                "donor_name": "",
                "anonymous": "on",
                "received_on": self.today.isoformat(),
                "donation_type": DonationRecord.DonationType.MONEY,
                "description": "",
                "amount": "125.00",
                "quantity": "",
                "unit": "",
                "destination": DonationRecord.Destination.GENERAL,
                "department": "",
                "event": "",
                "destination_description": "",
                "account": str(self.account.pk),
                "payment_method": FinancialTransaction.PaymentMethod.CASH,
            },
        )
        donation = DonationRecord.objects.get()
        entry = donation.financial_transaction

        response = self.client.post(
            reverse("donation-cancel", kwargs={"pk": donation.pk}),
            {"reason": "Registro lançado em duplicidade"},
        )

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(response.status_code, 302)
        donation.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(donation.status, DonationRecord.Status.CANCELLED)
        self.assertEqual(donation.cancellation_reason, "Registro lançado em duplicidade")
        self.assertEqual(entry.status, FinancialTransaction.Status.CANCELLED)
        self.assertIsNone(entry.account)
        self.assertIsNone(entry.settled_on)
        self.assertEqual(entry.audit_entries.count(), 2)

    def test_linked_donation_income_cannot_be_edited_as_regular_transaction(self):
        self.client.post(
            reverse("donation-create"),
            {
                "donor_name": "",
                "anonymous": "on",
                "received_on": self.today.isoformat(),
                "donation_type": DonationRecord.DonationType.MONEY,
                "description": "",
                "amount": "50.00",
                "quantity": "",
                "unit": "",
                "destination": DonationRecord.Destination.GENERAL,
                "department": "",
                "event": "",
                "destination_description": "",
                "account": str(self.account.pk),
                "payment_method": FinancialTransaction.PaymentMethod.CASH,
            },
        )
        entry = DonationRecord.objects.get().financial_transaction

        response = self.client.get(
            reverse("financial-transaction-update", kwargs={"pk": entry.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_dashboard_hides_account_balances_without_account_permission(self):
        user = get_user_model().objects.create_user(username="somente_lancamentos")
        permissions = Permission.objects.filter(
            content_type__app_label="financeiro",
            codename="view_financialtransaction",
        )
        user.user_permissions.add(*permissions)
        self.client.force_login(user)

        response = self.client.get(reverse("financial-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_accounts"])
        self.assertNotIn("account_balances", response.context)
        self.assertNotContains(response, "Saldos por conta")

    def test_transaction_create_records_creator_and_audit(self):
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(),
        )

        self.assertEqual(response.status_code, 302)
        entry = FinancialTransaction.objects.get(title="Dízimo")
        self.assertEqual(entry.created_by, self.user)
        self.assertEqual(entry.updated_by, self.user)
        audit = FinancialTransactionAudit.objects.get(transaction=entry)
        self.assertEqual(audit.action, FinancialTransactionAudit.Action.CREATED)
        self.assertEqual(audit.actor, self.user)
        self.assertIsNone(audit.before_data)
        self.assertEqual(audit.after_data["valor"], "250.00")

    def test_settled_income_and_expense_update_account_balance(self):
        self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(
                status=FinancialTransaction.Status.SETTLED,
                settled_on=self.today.isoformat(),
                account=self.account.pk,
            ),
        )
        self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(
                kind=FinancialTransaction.Kind.EXPENSE,
                title="Reparo",
                category=self.expense_category.pk,
                amount="80.00",
                status=FinancialTransaction.Status.SETTLED,
                settled_on=self.today.isoformat(),
                account=self.account.pk,
            ),
        )

        dashboard = self.client.get(reverse("financial-dashboard"))

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context["month_income"], Decimal("250.00"))
        self.assertEqual(dashboard.context["month_expense"], Decimal("80.00"))
        self.assertEqual(dashboard.context["month_net"], Decimal("170.00"))
        self.assertEqual(
            dashboard.context["account_balances"][0]["balance"],
            Decimal("270.00"),
        )

    def test_confirmed_pix_income_is_saved_with_category_and_audit(self):
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(
                title="Dízimo conferido",
                status=FinancialTransaction.Status.SETTLED,
                payment_method=FinancialTransaction.PaymentMethod.PIX,
                settled_on=self.today.isoformat(),
                account=self.account.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        entry = FinancialTransaction.objects.get(title="Dízimo conferido")
        self.assertEqual(entry.category, self.income_category)
        self.assertEqual(entry.payment_method, FinancialTransaction.PaymentMethod.PIX)
        audit = FinancialTransactionAudit.objects.get(transaction=entry)
        self.assertEqual(audit.after_data["forma_pagamento"], "Pix")

    def test_report_groups_confirmed_contributions_by_payment_method(self):
        FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Dízimo conferido",
            category=self.income_category,
            amount=Decimal("100.00"),
            due_on=self.today,
            status=FinancialTransaction.Status.SETTLED,
            payment_method=FinancialTransaction.PaymentMethod.PIX,
            settled_on=self.today,
            account=self.account,
        )
        FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Oferta conferida",
            category=self.offering_category,
            amount=Decimal("50.00"),
            due_on=self.today,
            status=FinancialTransaction.Status.SETTLED,
            payment_method=FinancialTransaction.PaymentMethod.CASH,
            settled_on=self.today,
            account=self.account,
        )
        FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Pix aguardando conferência",
            category=self.income_category,
            amount=Decimal("500.00"),
            due_on=self.today,
            payment_method=FinancialTransaction.PaymentMethod.PIX,
        )

        response = self.client.get(
            reverse("financial-report"),
            {
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        method_totals = {
            row["method_label"]: row["total"]
            for row in response.context["payment_method_rows"]
        }
        self.assertEqual(method_totals["Pix"], Decimal("100.00"))
        self.assertEqual(method_totals["Dinheiro"], Decimal("50.00"))
        self.assertEqual(response.context["income_total"], Decimal("150.00"))
        self.assertContains(response, "Pix aguardando conferência")

    def test_pending_transactions_do_not_change_account_balance(self):
        self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(),
        )

        dashboard = self.client.get(reverse("financial-dashboard"))

        self.assertEqual(dashboard.context["month_income"], Decimal("0.00"))
        self.assertEqual(
            dashboard.context["account_balances"][0]["balance"],
            Decimal("100.00"),
        )

    def test_settled_transaction_requires_account_and_settlement_date(self):
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(status=FinancialTransaction.Status.SETTLED),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("account", response.context["form"].errors)
        self.assertIn("settled_on", response.context["form"].errors)
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_date_input_uses_html_date_value_format(self):
        response = self.client.get(reverse("financial-transaction-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'value="{self.today.isoformat()}"',
        )

    def test_pending_transaction_cannot_move_an_account(self):
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(account=self.account.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("account", response.context["form"].errors)
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_category_must_match_transaction_type(self):
        response = self.client.post(
            reverse("financial-transaction-create"),
            self.transaction_data(
                kind=FinancialTransaction.Kind.EXPENSE,
                category=self.income_category.pk,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_update_records_before_and_after_values(self):
        entry = FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Dízimo",
            category=self.income_category,
            amount=Decimal("250.00"),
            due_on=self.today,
            created_by=self.user,
            updated_by=self.user,
        )
        response = self.client.post(
            reverse("financial-transaction-update", kwargs={"pk": entry.pk}),
            self.transaction_data(title="Dízimo especial", amount="300.00"),
        )

        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.title, "Dízimo especial")
        audit = FinancialTransactionAudit.objects.get(
            transaction=entry,
            action=FinancialTransactionAudit.Action.UPDATED,
        )
        self.assertEqual(audit.before_data["descrição"], "Dízimo")
        self.assertEqual(audit.before_data["valor"], "250.00")
        self.assertEqual(audit.after_data["descrição"], "Dízimo especial")
        self.assertEqual(audit.actor, self.user)

    def test_transaction_list_filters_by_kind_and_date(self):
        matching = FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Receita desta semana",
            category=self.income_category,
            amount=Decimal("50.00"),
            due_on=self.today,
        )
        FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.EXPENSE,
            title="Despesa anterior",
            category=self.expense_category,
            amount=Decimal("20.00"),
            due_on=self.today - timedelta(days=3),
        )

        response = self.client.get(
            reverse("financial-transaction-list"),
            {
                "kind": FinancialTransaction.Kind.INCOME,
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["transactions"]), [matching])

    def test_invalid_date_filter_is_reported(self):
        response = self.client.get(
            reverse("financial-transaction-list"),
            {"date_from": "not-a-date"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("date_from", response.context["filter_form"].errors)
        self.assertEqual(len(response.context["transactions"]), 0)

    def test_report_groups_settled_totals_by_department_and_event(self):
        department = Department.objects.create(name="Missões")
        now = timezone.now()
        event = ChurchEvent.objects.create(
            title="Conferência missionária",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
        )
        for kind, category, title, amount in (
            (
                FinancialTransaction.Kind.INCOME,
                self.income_category,
                "Oferta missionária",
                Decimal("120.00"),
            ),
            (
                FinancialTransaction.Kind.EXPENSE,
                self.expense_category,
                "Som da conferência",
                Decimal("40.00"),
            ),
        ):
            FinancialTransaction.objects.create(
                kind=kind,
                title=title,
                category=category,
                amount=amount,
                due_on=self.today,
                status=FinancialTransaction.Status.SETTLED,
                settled_on=self.today,
                account=self.account,
                department=department,
                event=event,
            )

        response = self.client.get(
            reverse("financial-report"),
            {
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["income_total"], Decimal("120.00"))
        self.assertEqual(response.context["expense_total"], Decimal("40.00"))
        self.assertEqual(response.context["net_total"], Decimal("80.00"))
        self.assertEqual(response.context["department_rows"][0]["net"], Decimal("80.00"))
        self.assertEqual(response.context["event_rows"][0]["income"], Decimal("120.00"))
        self.assertEqual(response.context["event_rows"][0]["expense"], Decimal("40.00"))
        self.assertContains(response, "Conferência missionária")
        self.assertContains(response, "Missões")

    def test_detail_shows_audit_history(self):
        entry = FinancialTransaction.objects.create(
            kind=FinancialTransaction.Kind.INCOME,
            title="Oferta",
            category=self.income_category,
            amount=Decimal("40.00"),
            due_on=self.today,
        )
        FinancialTransactionAudit.objects.create(
            transaction=entry,
            transaction_label=entry.title,
            action=FinancialTransactionAudit.Action.CREATED,
            after_data={"descrição": entry.title},
            actor=self.user,
        )

        response = self.client.get(
            reverse("financial-transaction-detail", kwargs={"pk": entry.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Histórico de alterações")
        self.assertContains(response, "Oferta")
        self.assertContains(response, "Ver registro")

    def test_categories_and_accounts_can_be_managed(self):
        category_response = self.client.post(
            reverse("financial-category-create"),
            {
                "name": "Contribuição especial",
                "kind": FinancialCategory.Kind.INCOME,
                "active": "on",
            },
        )
        account_response = self.client.post(
            reverse("financial-account-create"),
            {
                "name": "Caixa do templo",
                "kind": FinancialAccount.Kind.CASH,
                "opening_balance": "25.00",
                "active": "on",
            },
        )

        self.assertRedirects(
            category_response, reverse("financial-category-list")
        )
        self.assertRedirects(account_response, reverse("financial-account-list"))
        self.assertTrue(
            FinancialCategory.objects.filter(name="Contribuição especial").exists()
        )
        self.assertTrue(
            FinancialAccount.objects.filter(name="Caixa do templo").exists()
        )

    def test_pj_bank_account_stores_bank_and_one_legal_representative(self):
        response = self.client.post(
            reverse("financial-account-create"),
            {
                "name": "Conta da igreja",
                "kind": FinancialAccount.Kind.BANK,
                "bank_name": "Banco Exemplo",
                "branch": "1234",
                "account_number": "000123-4",
                "account_type": FinancialAccount.AccountType.CHECKING,
                "holder_type": FinancialAccount.HolderType.COMPANY,
                "holder_name": "Igreja Exemplo Ltda.",
                "cnpj": "12.345.678/0001-90",
                "legal_representative_name": "Ana da Silva",
                "legal_representative_cpf": "123.456.789-01",
                "opening_balance": "0.00",
                "active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("financial-account-list"),
        )
        account = FinancialAccount.objects.get(name="Conta da igreja")
        self.assertEqual(account.bank_name, "Banco Exemplo")
        self.assertEqual(account.branch, "1234")
        self.assertEqual(account.account_number, "000123-4")
        self.assertEqual(account.holder_type, FinancialAccount.HolderType.COMPANY)
        self.assertEqual(account.cnpj, "12345678000190")
        self.assertEqual(account.legal_representative_name, "Ana da Silva")
        self.assertEqual(account.legal_representative_cpf, "12345678901")

    def test_bank_account_requires_company_and_representative_data_for_pj(self):
        response = self.client.post(
            reverse("financial-account-create"),
            {
                "name": "Conta PJ incompleta",
                "kind": FinancialAccount.Kind.BANK,
                "bank_name": "Banco Exemplo",
                "branch": "1234",
                "account_number": "5678",
                "account_type": FinancialAccount.AccountType.CHECKING,
                "holder_type": FinancialAccount.HolderType.COMPANY,
                "holder_name": "Igreja Exemplo",
                "cnpj": "",
                "legal_representative_name": "",
                "legal_representative_cpf": "",
                "opening_balance": "0.00",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("cnpj", response.context["form"].errors)
        self.assertIn("legal_representative_name", response.context["form"].errors)
        self.assertIn("legal_representative_cpf", response.context["form"].errors)
        self.assertFalse(FinancialAccount.objects.filter(name="Conta PJ incompleta").exists())

    def test_bank_account_rejects_invalid_document_lengths(self):
        response = self.client.post(
            reverse("financial-account-create"),
            {
                "name": "Conta PJ documento inválido",
                "kind": FinancialAccount.Kind.BANK,
                "bank_name": "Banco Exemplo",
                "branch": "1234",
                "account_number": "5678",
                "account_type": FinancialAccount.AccountType.CHECKING,
                "holder_type": FinancialAccount.HolderType.COMPANY,
                "holder_name": "Igreja Exemplo",
                "cnpj": "123.456",
                "legal_representative_name": "Ana da Silva",
                "legal_representative_cpf": "123.456",
                "opening_balance": "0.00",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("cnpj", response.context["form"].errors)
        self.assertIn("legal_representative_cpf", response.context["form"].errors)
        self.assertFalse(
            FinancialAccount.objects.filter(name="Conta PJ documento inválido").exists()
        )

    def test_bank_account_masks_number_in_list_and_restricts_full_details(self):
        account = FinancialAccount.objects.create(
            name="Conta PJ",
            kind=FinancialAccount.Kind.BANK,
            bank_name="Banco Exemplo",
            branch="0001",
            account_number="98765432",
            account_type=FinancialAccount.AccountType.CHECKING,
            holder_type=FinancialAccount.HolderType.COMPANY,
            holder_name="Igreja Exemplo",
            cnpj="12345678000190",
            legal_representative_name="Ana da Silva",
            legal_representative_cpf="12345678901",
        )

        list_response = self.client.get(reverse("financial-account-list"))
        detail_response = self.client.get(
            reverse("financial-account-detail", kwargs={"pk": account.pk})
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "••••5432")
        self.assertNotContains(list_response, "98765432")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Banco Exemplo")
        self.assertContains(detail_response, "12345678000190")
        self.assertContains(detail_response, "12345678901")

        no_account_permission = get_user_model().objects.create_user(
            username="sem_acesso_contas"
        )
        no_account_permission.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="financeiro",
                codename="view_financialtransaction",
            )
        )
        self.client.force_login(no_account_permission)
        denied_response = self.client.get(
            reverse("financial-account-detail", kwargs={"pk": account.pk})
        )
        self.assertEqual(denied_response.status_code, 403)

    def test_individual_bank_account_does_not_require_company_representative(self):
        response = self.client.post(
            reverse("financial-account-create"),
            {
                "name": "Conta pessoal",
                "kind": FinancialAccount.Kind.BANK,
                "bank_name": "Banco Exemplo",
                "branch": "0001",
                "account_number": "001122-3",
                "account_type": FinancialAccount.AccountType.SAVINGS,
                "holder_type": FinancialAccount.HolderType.INDIVIDUAL,
                "holder_name": "Marta Santos",
                "cnpj": "",
                "legal_representative_name": "",
                "legal_representative_cpf": "",
                "opening_balance": "0.00",
                "active": "on",
            },
        )

        self.assertRedirects(response, reverse("financial-account-list"))
        account = FinancialAccount.objects.get(name="Conta pessoal")
        self.assertEqual(account.holder_type, FinancialAccount.HolderType.INDIVIDUAL)
        self.assertEqual(account.legal_representative_name, "")
