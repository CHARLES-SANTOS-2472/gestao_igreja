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



class PixKeyAndMachineTests(TestCase):
    def setUp(self):
        from .models import CardMachine, FinancialAccount, PixKey

        self.PixKey, self.CardMachine = PixKey, CardMachine
        self.user = get_user_model().objects.create_superuser("adm", password="x")
        self.client.force_login(self.user)
        self.account = FinancialAccount.objects.create(name="Caixa")

    def key_data(self, **extra):
        data = {
            "label": "Principal",
            "account": self.account.pk,
            "key_type": "cnpj",
            "key": "36.605.928/0001-47",
            "receiver_name": "Igreja Exemplo",
            "city": "Sao Paulo",
            "is_default": "on",
            "active": "on",
        }
        data.update(extra)
        return data

    def test_create_key_normalizes_and_is_used_in_qr(self):
        response = self.client.post(reverse("pix-key-create"), self.key_data())
        self.assertRedirects(response, reverse("pix-key-list"))
        key = self.PixKey.objects.get()
        self.assertEqual(key.key, "36605928000147")
        page = self.client.get(reverse("financial-pix"))
        self.assertContains(page, "Igreja Exemplo".replace(" ", "")[:0] + "5914Igreja Exemplo")

    def test_invalid_and_duplicate_key(self):
        bad = self.client.post(reverse("pix-key-create"), self.key_data(key="123"))
        self.assertEqual(bad.status_code, 200)
        self.client.post(reverse("pix-key-create"), self.key_data())
        dup = self.client.post(reverse("pix-key-create"), self.key_data(label="Outra"))
        self.assertEqual(dup.status_code, 200)
        self.assertEqual(self.PixKey.objects.count(), 1)

    def test_only_one_default(self):
        self.client.post(reverse("pix-key-create"), self.key_data())
        self.client.post(
            reverse("pix-key-create"),
            self.key_data(label="Pessoal", key_type="email", key="A@b.com"),
        )
        self.assertEqual(self.PixKey.objects.filter(is_default=True).count(), 1)
        self.assertTrue(self.PixKey.objects.get(label="Pessoal").is_default)

    def test_machine_and_prefilled_card_registration(self):
        response = self.client.post(
            reverse("card-machine-create"),
            {"name": "Maquininha 1", "provider": "X", "terminal_id": "1", "account": self.account.pk, "active": "on"},
        )
        self.assertRedirects(response, reverse("card-machine-list"))
        page = self.client.get(reverse("financial-pix"), {"valor": "50"})
        self.assertContains(page, "forma=debit_card")
        category = FinancialCategory.objects.get(name="Dízimos")
        form = self.client.get(
            reverse("financial-transaction-create"),
            {"categoria": category.pk, "forma": "debit_card", "conta": self.account.pk, "valor": "50"},
        ).context["form"]
        self.assertEqual(form.initial["payment_method"], "debit_card")
        self.assertEqual(form.initial["account"], self.account)
        self.assertEqual(str(form.initial["amount"]), "50.00")
