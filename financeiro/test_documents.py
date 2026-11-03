from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DonationRecord


class FinancialDocumentsTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser("chefe", "c@x.com", "senha-Forte-123")
        self.client.force_login(admin)

    def test_report_pdf_and_csv(self):
        url = reverse("financial-report")
        pdf = self.client.get(url, {"date_from": "2026-01-01", "date_to": "2026-01-31", "formato": "pdf"})
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        csv_response = self.client.get(url, {"formato": "csv"})
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn("Receitas recebidas", csv_response.content.decode("utf-8-sig"))

    def test_invalid_period_falls_back_to_page(self):
        response = self.client.get(
            reverse("financial-report"),
            {"date_from": "2026-02-01", "date_to": "2026-01-01", "formato": "pdf"},
        )
        self.assertEqual(response["Content-Type"].split(";")[0], "text/html")

    def test_donation_receipt(self):
        donation = DonationRecord.objects.create(
            donor_name="Maria", received_on=date(2026, 1, 5),
            donation_type=DonationRecord.DonationType.MONEY, amount=Decimal("50.00"),
            destination=DonationRecord.Destination.GENERAL,
        )
        response = self.client.get(reverse("donation-receipt", args=[donation.pk]))
        self.assertTrue(response.content.startswith(b"%PDF"))
        detail = self.client.get(reverse("donation-detail", args=[donation.pk]))
        self.assertContains(detail, "Emitir recibo")
        donation.status = DonationRecord.Status.CANCELLED
        donation.save()
        self.assertEqual(self.client.get(reverse("donation-receipt", args=[donation.pk])).status_code, 302)

    def test_receipt_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("donation-receipt", args=[1])).status_code, 302)
