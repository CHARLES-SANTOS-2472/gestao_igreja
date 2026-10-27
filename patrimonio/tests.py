from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AdministrativeTask,
    AdministrativeTaskAudit,
    AssetMaintenance,
    ChurchAsset,
    Contract,
    Supplier,
)


class AssetManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="patrimonio")
        permissions = Permission.objects.filter(
            content_type__app_label="patrimonio",
            codename__in=(
                "view_churchasset",
                "add_churchasset",
                "change_churchasset",
                "view_assetmaintenance",
                "add_assetmaintenance",
                "view_supplier",
                "add_supplier",
                "change_supplier",
                "view_contract",
                "add_contract",
                "change_contract",
                "view_administrativetask",
                "add_administrativetask",
                "change_administrativetask",
            ),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)
        self.asset = ChurchAsset.objects.create(
            name="Teclado",
            category=ChurchAsset.Category.INSTRUMENT,
            asset_tag="PAT-001",
            location="Templo",
        )

    def test_asset_pages_require_specific_permissions(self):
        user = get_user_model().objects.create_user(username="sem_patrimonio")
        self.client.force_login(user)

        response = self.client.get(reverse("asset-list"))

        self.assertEqual(response.status_code, 403)

    def test_asset_list_can_search_and_filter(self):
        response = self.client.get(reverse("asset-list"), {"q": "PAT-001"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teclado")
        self.assertNotContains(response, "Nenhum bem cadastrado")

    def test_create_asset_stores_location_and_acquisition_data(self):
        response = self.client.post(
            reverse("asset-create"),
            {
                "name": "Notebook",
                "category": ChurchAsset.Category.COMPUTER,
                "asset_tag": "PAT-002",
                "serial_number": "SERIAL-123",
                "location": "Secretaria",
                "status": ChurchAsset.Status.ACTIVE,
                "acquired_on": "2026-01-15",
                "purchase_value": "3500.00",
                "description": "Equipamento da secretaria",
            },
        )

        self.assertEqual(response.status_code, 302)
        asset = ChurchAsset.objects.get(asset_tag="PAT-002")
        self.assertEqual(asset.location, "Secretaria")
        self.assertEqual(asset.purchase_value, Decimal("3500.00"))

    def test_asset_tag_must_be_unique(self):
        response = self.client.post(
            reverse("asset-create"),
            {
                "name": "Outro teclado",
                "category": ChurchAsset.Category.INSTRUMENT,
                "asset_tag": "PAT-001",
                "location": "",
                "status": ChurchAsset.Status.ACTIVE,
                "acquired_on": "",
                "purchase_value": "",
                "description": "",
                "serial_number": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("asset_tag", response.context["form"].errors)
        self.assertEqual(ChurchAsset.objects.count(), 1)

    def test_maintenance_record_tracks_user_and_is_shown_on_asset(self):
        today = timezone.localdate()
        response = self.client.post(
            reverse("asset-maintenance-create", kwargs={"asset_pk": self.asset.pk}),
            {
                "maintenance_date": today.isoformat(),
                "description": "Revisão preventiva",
                "cost": "120.00",
                "performed_by": "Técnico responsável",
                "next_maintenance_on": (today + timedelta(days=180)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)
        maintenance = AssetMaintenance.objects.get(asset=self.asset)
        self.assertEqual(maintenance.recorded_by, self.user)
        self.assertEqual(maintenance.cost, Decimal("120.00"))
        detail = self.client.get(
            reverse("asset-detail", kwargs={"pk": self.asset.pk})
        )
        self.assertContains(detail, "Revisão preventiva")

    def test_maintenance_rejects_next_date_before_service_date(self):
        today = timezone.localdate()
        response = self.client.post(
            reverse("asset-maintenance-create", kwargs={"asset_pk": self.asset.pk}),
            {
                "maintenance_date": today.isoformat(),
                "description": "Revisão",
                "cost": "0.00",
                "performed_by": "",
                "next_maintenance_on": (today - timedelta(days=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("next_maintenance_on", response.context["form"].errors)
        self.assertFalse(AssetMaintenance.objects.exists())

    def test_user_without_maintenance_permission_does_not_see_records(self):
        AssetMaintenance.objects.create(
            asset=self.asset,
            maintenance_date=timezone.localdate(),
            description="Serviço restrito",
        )
        user = get_user_model().objects.create_user(username="somente_bens")
        permission = Permission.objects.get(
            content_type__app_label="patrimonio",
            codename="view_churchasset",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("asset-detail", kwargs={"pk": self.asset.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Histórico de manutenção")
        self.assertNotContains(response, "Serviço restrito")

    def test_supplier_cnpj_is_normalized_and_can_be_searched(self):
        response = self.client.post(
            reverse("supplier-create"),
            {
                "name": "Fornecedor Exemplo",
                "cnpj": "12.345.678/0001-90",
                "contact_name": "Ana",
                "phone": "(11) 99999-0000",
                "email": "contato@example.com",
                "notes": "",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        supplier = Supplier.objects.get(name="Fornecedor Exemplo")
        self.assertEqual(supplier.cnpj, "12345678000190")
        search = self.client.get(
            reverse("supplier-list"), {"q": "contato@example.com"}
        )
        self.assertContains(search, "Fornecedor Exemplo")

    def test_supplier_rejects_invalid_cnpj_length(self):
        response = self.client.post(
            reverse("supplier-create"),
            {
                "name": "Fornecedor CNPJ inválido",
                "cnpj": "12345",
                "contact_name": "",
                "phone": "",
                "email": "",
                "notes": "",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("cnpj", response.context["form"].errors)
        self.assertFalse(Supplier.objects.filter(name="Fornecedor CNPJ inválido").exists())

    def test_contract_requires_valid_dates_and_links_supplier(self):
        supplier = Supplier.objects.create(name="Prestador")
        response = self.client.post(
            reverse("contract-create"),
            {
                "title": "Manutenção anual",
                "contract_number": "CTR-001",
                "supplier": supplier.pk,
                "start_date": "2026-12-01",
                "end_date": "2026-11-30",
                "value": "1200.00",
                "status": Contract.Status.ACTIVE,
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("end_date", response.context["form"].errors)
        self.assertFalse(Contract.objects.exists())

    def test_contract_can_be_created_and_is_linked_to_supplier(self):
        supplier = Supplier.objects.create(name="Fornecedor contrato")
        response = self.client.post(
            reverse("contract-create"),
            {
                "title": "Internet da igreja",
                "contract_number": "NET-2026",
                "supplier": supplier.pk,
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
                "value": "2400.00",
                "status": Contract.Status.ACTIVE,
                "notes": "Plano anual",
            },
        )

        self.assertEqual(response.status_code, 302)
        contract = Contract.objects.get(contract_number="NET-2026")
        self.assertEqual(contract.supplier, supplier)
        self.assertEqual(contract.value, Decimal("2400.00"))

    def test_contract_list_highlights_expiring_and_overdue_contracts(self):
        supplier = Supplier.objects.create(name="Prestador")
        today = timezone.localdate()
        expiring = Contract.objects.create(
            title="Contrato vencendo",
            supplier=supplier,
            start_date=today - timedelta(days=300),
            end_date=today + timedelta(days=10),
        )
        overdue = Contract.objects.create(
            title="Contrato vencido",
            supplier=supplier,
            start_date=today - timedelta(days=400),
            end_date=today - timedelta(days=5),
        )

        response = self.client.get(reverse("contract-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contrato vencendo")
        self.assertContains(response, "Contrato vencido")
        self.assertContains(response, "10 dia(s)")
        self.assertContains(response, "Vencido")
        self.assertEqual(response.context["overdue_contract_count"], 1)
        self.assertEqual(response.context["expiring_contracts"][0].pk, expiring.pk)
        self.assertNotEqual(response.context["expiring_contracts"][0].pk, overdue.pk)

    def test_contract_list_filters_cancelled_contracts(self):
        supplier = Supplier.objects.create(name="Prestador")
        today = timezone.localdate()
        Contract.objects.create(
            title="Contrato cancelado",
            supplier=supplier,
            start_date=today,
            end_date=today + timedelta(days=60),
            status=Contract.Status.CANCELLED,
        )
        response = self.client.get(reverse("contract-list"), {"state": "cancelled"})

        self.assertContains(response, "Contrato cancelado")
        self.assertEqual(len(response.context["contracts"]), 1)

    def test_create_task_tracks_creator_assignee_and_due_date(self):
        response = self.client.post(
            reverse("task-create"),
            {
                "title": "Revisar extintores",
                "description": "Conferir validade dos equipamentos.",
                "due_date": "2026-11-10",
                "priority": AdministrativeTask.Priority.HIGH,
                "status": AdministrativeTask.Status.OPEN,
                "assigned_to": self.user.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        task = AdministrativeTask.objects.get(title="Revisar extintores")
        self.assertEqual(task.assigned_to, self.user)
        self.assertEqual(task.created_by, self.user)
        self.assertIsNone(task.completed_at)
        audit = task.audit_entries.get()
        self.assertEqual(audit.action, "created")
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.after_data["responsável"], self.user.username)

    def test_completing_and_reopening_task_updates_completion_timestamp(self):
        task = AdministrativeTask.objects.create(
            title="Organizar depósito",
            status=AdministrativeTask.Status.OPEN,
        )
        completed = self.client.post(
            reverse("task-update", kwargs={"pk": task.pk}),
            {
                "title": task.title,
                "description": "",
                "due_date": "",
                "priority": AdministrativeTask.Priority.NORMAL,
                "status": AdministrativeTask.Status.COMPLETED,
                "assigned_to": "",
            },
        )

        self.assertEqual(completed.status_code, 302)
        task.refresh_from_db()
        completed_at = task.completed_at
        self.assertIsNotNone(completed_at)
        completed_audit = task.audit_entries.latest("created_at")
        self.assertEqual(completed_audit.before_data["situação"], "Pendente")
        self.assertEqual(completed_audit.after_data["situação"], "Concluída")

        reopened = self.client.post(
            reverse("task-update", kwargs={"pk": task.pk}),
            {
                "title": task.title,
                "description": "",
                "due_date": "",
                "priority": AdministrativeTask.Priority.NORMAL,
                "status": AdministrativeTask.Status.IN_PROGRESS,
                "assigned_to": "",
            },
        )

        self.assertEqual(reopened.status_code, 302)
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.audit_entries.count(), 2)
        self.assertEqual(
            task.audit_entries.latest("created_at").after_data["situação"],
            "Em andamento",
        )

    def test_task_list_filters_status_and_shows_overdue_count(self):
        today = timezone.localdate()
        AdministrativeTask.objects.create(
            title="Inspecionar telhado",
            due_date=today - timedelta(days=1),
            status=AdministrativeTask.Status.OPEN,
        )
        AdministrativeTask.objects.create(
            title="Revisar documentação",
            due_date=today,
            status=AdministrativeTask.Status.COMPLETED,
        )

        response = self.client.get(
            reverse("task-list"), {"status": AdministrativeTask.Status.OPEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inspecionar telhado")
        self.assertNotContains(response, "Revisar documentação")
        self.assertEqual(response.context["open_count"], 1)
        self.assertEqual(response.context["overdue_count"], 1)

    def test_task_dashboard_shows_my_tasks_and_upcoming_deadlines(self):
        today = timezone.localdate()
        my_task = AdministrativeTask.objects.create(
            title="Minha tarefa",
            due_date=today + timedelta(days=2),
            assigned_to=self.user,
        )
        other_task = AdministrativeTask.objects.create(
            title="Tarefa de outro responsável",
            due_date=today + timedelta(days=4),
        )
        AdministrativeTask.objects.create(
            title="Prazo distante",
            due_date=today + timedelta(days=10),
        )

        response = self.client.get(reverse("task-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [task.pk for task in response.context["my_open_tasks"]],
            [my_task.pk],
        )
        self.assertEqual(
            {task.pk for task in response.context["due_soon_tasks"]},
            {my_task.pk, other_task.pk},
        )
        self.assertEqual(response.context["due_soon_count"], 2)

    def test_task_detail_shows_audit_and_is_restricted_to_view_permission(self):
        task = AdministrativeTask.objects.create(
            title="Preparar ata",
            description="Separar os documentos.",
            created_by=self.user,
        )
        AdministrativeTaskAudit.objects.create(
            task=task,
            task_title=task.title,
            action=AdministrativeTaskAudit.Action.CREATED,
            after_data={"título": task.title},
            actor=self.user,
        )

        response = self.client.get(reverse("task-detail", kwargs={"pk": task.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Separar os documentos.")
        self.assertContains(response, "Histórico de alterações")
        self.assertContains(response, "Ver registro")

    def test_task_views_require_task_specific_permission(self):
        user = get_user_model().objects.create_user(username="sem_tarefas")
        permission = Permission.objects.get(
            content_type__app_label="patrimonio",
            codename="view_churchasset",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("task-list"))

        self.assertEqual(response.status_code, 403)

    def test_supplier_and_contract_lists_require_their_own_permissions(self):
        user = get_user_model().objects.create_user(username="sem_fornecedor_contrato")
        permission = Permission.objects.get(
            content_type__app_label="patrimonio",
            codename="view_churchasset",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        supplier_response = self.client.get(reverse("supplier-list"))
        contract_response = self.client.get(reverse("contract-list"))

        self.assertEqual(supplier_response.status_code, 403)
        self.assertEqual(contract_response.status_code, 403)
