from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import FinancialCategory, FinancialTransaction
from .pix import build_pix_payload, crc16


class PixPayloadTests(TestCase):
    def test_crc16_reference_vector(self):
        self.assertEqual(crc16("123456789"), "29B1")

    def test_payload_structure_and_checksum(self):
        payload = build_pix_payload(
            "36605928000147", "Igreja Évangélica", "São Paulo", "25.5", "DIZIMO"
        )
        self.assertTrue(payload.startswith("000201"))
        self.assertIn("0014br.gov.bcb.pix0114" + "36605928000147", payload)
        self.assertIn("540525.50", payload)
        self.assertIn("0506DIZIMO", payload)
        self.assertEqual(payload[-4:], crc16(payload[:-4]))

    def test_payload_without_amount(self):
        payload = build_pix_payload("36605928000147", "Igreja", "Cidade")
        self.assertNotIn("540", payload.split("5802BR")[0][-12:])
        self.assertIn("0503***", payload)


class PixViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tes", password="x")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="financeiro",
                codename__in=["view_financialtransaction", "add_financialtransaction"],
            )
        )
        self.client.force_login(self.user)

    def test_offering_page_has_qr_and_reference(self):
        response = self.client.get(reverse("financial-pix"), {"tipo": "oferta", "valor": "10,00"})
        self.assertContains(response, "<svg")
        self.assertContains(response, "0506OFERTA")
        self.assertContains(response, "540510.00")

    def test_invalid_input_falls_back(self):
        response = self.client.get(reverse("financial-pix"), {"tipo": "x", "valor": "abc"})
        self.assertContains(response, "0506DIZIMO")

    def test_requires_permission(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("financial-pix")).status_code, 302)

    def test_create_form_prefilled_from_pix(self):
        category = FinancialCategory.objects.get(
            name="Dízimos", kind=FinancialCategory.Kind.INCOME
        )
        response = self.client.get(
            reverse("financial-transaction-create"),
            {"categoria": category.pk, "titulo": "Dízimo"},
        )
        form = response.context["form"]
        self.assertEqual(form.initial["category"], category)
        self.assertEqual(
            form.initial["payment_method"], FinancialTransaction.PaymentMethod.PIX
        )

