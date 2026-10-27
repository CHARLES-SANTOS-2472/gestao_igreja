from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AssistanceRecord, AssistedFamily


class SocialAssistanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="assistencia")
        permissions = Permission.objects.filter(
            content_type__app_label="assistencia_social",
            codename__in=(
                "view_assistedfamily",
                "add_assistedfamily",
                "change_assistedfamily",
                "view_assistancerecord",
                "add_assistancerecord",
                "change_assistancerecord",
            ),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)
        self.family = AssistedFamily.objects.create(
            reference_name="Família Exemplo",
            contact_name="Pessoa de Contato",
            phone="11999990000",
            neighborhood="Centro",
            postal_code="01001000",
            street="Rua Exemplo",
            number="10",
            city="São Paulo",
            state="SP",
            household_size=4,
            created_by=self.user,
        )

    def test_social_assistance_requires_specific_permissions(self):
        user = get_user_model().objects.create_user(username="sem_assistencia")
        self.client.force_login(user)

        family_list = self.client.get(reverse("assisted-family-list"))
        aid_list = self.client.get(reverse("assistance-list"))

        self.assertEqual(family_list.status_code, 403)
        self.assertEqual(aid_list.status_code, 403)

    def test_write_permission_does_not_grant_read_access_to_family_data(self):
        user = get_user_model().objects.create_user(username="somente_cadastro")
        permission = Permission.objects.get(
            content_type__app_label="assistencia_social",
            codename="add_assistedfamily",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("assisted-family-create"))

        self.assertEqual(response.status_code, 403)

    def test_aid_history_requires_family_and_assistance_permissions(self):
        user = get_user_model().objects.create_user(username="somente_historico")
        permission = Permission.objects.get(
            content_type__app_label="assistencia_social",
            codename="view_assistancerecord",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("assistance-list"))

        self.assertEqual(response.status_code, 403)

    def test_assistance_export_requires_family_and_assistance_permissions(self):
        user = get_user_model().objects.create_user(username="sem_permissao_export")
        self.client.force_login(user)

        response = self.client.get(reverse("assistance-export-pdf"))

        self.assertEqual(response.status_code, 403)

    def test_family_can_be_created_and_searched(self):
        response = self.client.post(
            reverse("assisted-family-create"),
            {
                "reference_name": "Família do Bairro",
                "contact_name": "Contato Local",
                "phone": "11988887777",
                "postal_code": "01001-000",
                "street": "Rua Um",
                "number": "25",
                "address_extra": "Casa 2",
                "neighborhood": "Vila Nova",
                "city": "Campinas",
                "state": "SP",
                "household_size": "3",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        family = AssistedFamily.objects.get(reference_name="Família do Bairro")
        self.assertEqual(family.created_by, self.user)
        self.assertEqual(family.postal_code, "01001-000")
        self.assertEqual(family.street, "Rua Um")
        self.assertEqual(family.number, "25")
        self.assertEqual(family.address_extra, "Casa 2")
        self.assertEqual(family.city, "Campinas")
        search = self.client.get(
            reverse("assisted-family-list"), {"q": "11988887777"}
        )
        self.assertContains(search, "Família do Bairro")
        self.assertContains(search, "Campinas/SP")

    def test_family_detail_shows_google_maps_button_and_privacy_notice(self):
        response = self.client.get(
            reverse("assisted-family-detail", kwargs={"pk": self.family.pk})
        )

        self.assertContains(response, "Abrir endereço no Google Maps")
        self.assertContains(response, "query=Rua%20Exemplo")
        self.assertContains(response, "endereço acima será enviado ao Google")
        self.assertContains(response, "01001000")
        self.assertContains(response, "target=\"_blank\"")

    def test_legacy_address_is_preserved_when_editing_structured_address(self):
        self.family.address = "Rua Antiga, 20, Bairro Centro"
        self.family.save()

        response = self.client.post(
            reverse(
                "assisted-family-update", kwargs={"pk": self.family.pk}
            ),
            {
                "reference_name": self.family.reference_name,
                "contact_name": self.family.contact_name,
                "phone": self.family.phone,
                "postal_code": "01001000",
                "street": "Rua Atualizada",
                "number": "30",
                "address_extra": "",
                "neighborhood": "Centro",
                "city": "São Paulo",
                "state": "SP",
                "household_size": "4",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.family.refresh_from_db()
        self.assertEqual(self.family.address, "Rua Antiga, 20, Bairro Centro")
        self.assertEqual(self.family.street, "Rua Atualizada")

    def test_legacy_address_is_used_for_maps_until_street_is_migrated(self):
        self.family.street = ""
        self.family.number = ""
        self.family.address = "Rua Antiga, 20, Bairro Centro"
        self.family.save()

        response = self.client.get(
            reverse("assisted-family-detail", kwargs={"pk": self.family.pk})
        )

        self.assertContains(response, "Rua Antiga, 20, Bairro Centro")
        self.assertContains(response, "query=Rua%20Antiga")

    def test_family_page_hides_aid_history_without_aid_view_permission(self):
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FOOD_BASKET,
            description="Cesta registrada",
            assistance_date=timezone.localdate(),
            status=AssistanceRecord.Status.DELIVERED,
        )
        user = get_user_model().objects.create_user(username="consulta_familias")
        permission = Permission.objects.get(
            content_type__app_label="assistencia_social",
            codename="view_assistedfamily",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(
            reverse("assisted-family-detail", kwargs={"pk": self.family.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rua Exemplo")
        self.assertContains(response, "Abrir endereço no Google Maps")
        self.assertNotContains(response, "Cesta registrada")
        self.assertNotContains(response, "Ajudas sociais")

    def test_delivered_assistance_records_the_delivering_user(self):
        response = self.client.post(
            reverse("assistance-create", kwargs={"family_pk": self.family.pk}),
            {
                "aid_type": AssistanceRecord.AidType.FOOD_BASKET,
                "description": "Cesta básica",
                "quantity": "1",
                "amount": "",
                "assistance_date": timezone.localdate().isoformat(),
                "status": AssistanceRecord.Status.DELIVERED,
            },
        )

        self.assertEqual(response.status_code, 302)
        record = AssistanceRecord.objects.get(family=self.family)
        self.assertEqual(record.recorded_by, self.user)
        self.assertEqual(record.delivered_by, self.user)
        self.assertEqual(record.status, AssistanceRecord.Status.DELIVERED)

    def test_updating_planned_assistance_to_delivered_tracks_current_user(self):
        record = AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.HYGIENE,
            assistance_date=timezone.localdate(),
            status=AssistanceRecord.Status.PLANNED,
            recorded_by=self.user,
        )
        second_user = get_user_model().objects.create_user(username="entregador")
        permission = Permission.objects.filter(
            content_type__app_label="assistencia_social",
            codename__in=(
                "view_assistedfamily",
                "view_assistancerecord",
                "change_assistancerecord",
            ),
        )
        second_user.user_permissions.add(*permission)
        self.client.force_login(second_user)

        response = self.client.post(
            reverse("assistance-update", kwargs={"pk": record.pk}),
            {
                "aid_type": AssistanceRecord.AidType.HYGIENE,
                "description": "",
                "quantity": "2",
                "amount": "",
                "assistance_date": timezone.localdate().isoformat(),
                "status": AssistanceRecord.Status.DELIVERED,
            },
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.delivered_by, second_user)
        self.assertEqual(record.quantity, 2)

    def test_assistance_list_filters_date_range_and_status(self):
        today = timezone.localdate()
        record = AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FOOD,
            assistance_date=today,
            status=AssistanceRecord.Status.DELIVERED,
        )
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.CLOTHING,
            assistance_date=today + timedelta(days=1),
            status=AssistanceRecord.Status.PLANNED,
        )

        response = self.client.get(
            reverse("assistance-list"),
            {
                "status": AssistanceRecord.Status.DELIVERED,
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item.pk for item in response.context["assistance_records"]],
            [record.pk],
        )

    def test_assistance_report_totals_follow_selected_filters(self):
        today = timezone.localdate()
        delivered_financial = AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FINANCIAL,
            amount=Decimal("250.00"),
            assistance_date=today,
            status=AssistanceRecord.Status.DELIVERED,
        )
        delivered_food = AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FOOD,
            quantity=3,
            assistance_date=today,
            status=AssistanceRecord.Status.DELIVERED,
        )
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FINANCIAL,
            amount=Decimal("100.00"),
            assistance_date=today,
            status=AssistanceRecord.Status.PLANNED,
        )

        response = self.client.get(
            reverse("assistance-list"),
            {
                "status": AssistanceRecord.Status.DELIVERED,
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resumo por tipo de ajuda")
        self.assertContains(response, "Ajuda financeira entregue")
        self.assertContains(response, "250,00")
        self.assertEqual(response.context["report_summary"]["total_count"], 2)
        self.assertEqual(response.context["report_summary"]["delivered_count"], 2)
        self.assertEqual(response.context["report_summary"]["planned_count"], 0)
        self.assertEqual(response.context["report_summary"]["cancelled_count"], 0)
        self.assertEqual(
            response.context["report_summary"]["delivered_financial_total"],
            Decimal("250.00"),
        )
        rows_by_type = {
            row["aid_type"]: row for row in response.context["aid_type_rows"]
        }
        self.assertEqual(
            rows_by_type[AssistanceRecord.AidType.FINANCIAL]["delivered_amount"],
            Decimal("250.00"),
        )
        self.assertEqual(
            rows_by_type[AssistanceRecord.AidType.FOOD]["delivered_quantity"], 3
        )
        self.assertEqual(
            {item.pk for item in response.context["assistance_records"]},
            {delivered_financial.pk, delivered_food.pk},
        )

    def test_assistance_export_respects_filters_and_protects_spreadsheet_text(self):
        today = timezone.localdate()
        self.family.reference_name = "=2+2"
        self.family.save()
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FINANCIAL,
            description="+SUM(A1:A2)",
            amount=Decimal("250.00"),
            assistance_date=today,
            status=AssistanceRecord.Status.DELIVERED,
        )
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FOOD,
            quantity=3,
            assistance_date=today,
            status=AssistanceRecord.Status.PLANNED,
        )

        response = self.client.get(
            reverse("assistance-export-pdf"),
            {
                "status": AssistanceRecord.Status.DELIVERED,
                "aid_type": AssistanceRecord.AidType.FINANCIAL,
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", response.content)
        self.assertGreater(len(response.content), 2000)

    def test_assistance_export_returns_bad_request_for_invalid_filters(self):
        today = timezone.localdate()

        response = self.client.get(
            reverse("assistance-export-pdf"),
            {
                "date_from": (today + timedelta(days=1)).isoformat(),
                "date_to": today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Filtros inválidos", status_code=400)

    def test_financial_assistance_requires_and_records_amount(self):
        url = reverse("assistance-create", kwargs={"family_pk": self.family.pk})
        response = self.client.post(
            url,
            {
                "aid_type": AssistanceRecord.AidType.FINANCIAL,
                "description": "Ajuda emergencial",
                "quantity": "1",
                "amount": "",
                "assistance_date": timezone.localdate().isoformat(),
                "status": AssistanceRecord.Status.DELIVERED,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("amount", response.context["form"].errors)
        self.assertFalse(AssistanceRecord.objects.exists())

        response = self.client.post(
            url,
            {
                "aid_type": AssistanceRecord.AidType.FINANCIAL,
                "description": "Ajuda emergencial",
                "quantity": "1",
                "amount": "250.00",
                "assistance_date": timezone.localdate().isoformat(),
                "status": AssistanceRecord.Status.DELIVERED,
            },
        )

        self.assertEqual(response.status_code, 302)
        record = AssistanceRecord.objects.get(family=self.family)
        self.assertEqual(record.amount, Decimal("250.00"))

    def test_non_financial_assistance_rejects_amount(self):
        response = self.client.post(
            reverse("assistance-create", kwargs={"family_pk": self.family.pk}),
            {
                "aid_type": AssistanceRecord.AidType.FOOD_BASKET,
                "description": "Cesta",
                "quantity": "1",
                "amount": "100.00",
                "assistance_date": timezone.localdate().isoformat(),
                "status": AssistanceRecord.Status.PLANNED,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("amount", response.context["form"].errors)
        self.assertFalse(AssistanceRecord.objects.exists())

    def test_assistance_filter_rejects_invalid_or_reversed_dates_without_error(self):
        today = timezone.localdate()
        response = self.client.get(
            reverse("assistance-list"),
            {
                "date_from": (today + timedelta(days=1)).isoformat(),
                "date_to": today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["filter_form"].errors)
        self.assertEqual(len(response.context["assistance_records"]), 0)
        self.assertEqual(response.context["report_summary"]["total_count"], 0)
        self.assertEqual(len(response.context["aid_type_rows"]), 0)

    def test_family_cannot_be_deleted_while_assistance_records_exist(self):
        AssistanceRecord.objects.create(
            family=self.family,
            aid_type=AssistanceRecord.AidType.FOOD,
            assistance_date=timezone.localdate(),
        )

        with self.assertRaises(ProtectedError):
            self.family.delete()

        self.assertTrue(AssistedFamily.objects.filter(pk=self.family.pk).exists())
