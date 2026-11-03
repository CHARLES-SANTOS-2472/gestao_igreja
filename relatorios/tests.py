from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from financeiro.models import DonationRecord
from membros.models import Member
from ministerios.models import Department, DepartmentActivity

from .models import SavedReport
from .registry import REPORTS


class ReportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("chefe", "c@x.com", "senha-Forte-123")
        self.client.force_login(self.admin)
        self.leader = Member.objects.create(first_name="Ana", last_name="Lima", status="member",
                                            birth_date=date(1990, timezone.localdate().month, 5))
        self.dept = Department.objects.create(name="Louvor", leader=self.leader)
        DepartmentActivity.objects.create(
            department=self.dept, title="Ensaio", starts_at=timezone.now(), ends_at=timezone.now()
        )
        DonationRecord.objects.create(
            donor_name="Maria", received_on=timezone.localdate(),
            donation_type="money", amount=Decimal("20.00"), destination="general",
        )

    def test_every_report_previews_and_downloads(self):
        for report in REPORTS:
            args = [report.key] + ([self.dept.pk] if report.scoped else [])
            url = reverse("report-scoped" if report.scoped else "report", args=args)
            self.assertEqual(self.client.get(url).status_code, 200, report.key)
            for action, kind in (("pdf", "application/pdf"), ("csv", "text/csv")):
                response = self.client.post(url, {"acao": action, "recommendations": "Comprar cadeiras", "introduction": "Intro"})
                self.assertEqual(response.status_code, 200, report.key)
                self.assertIn(kind, response["Content-Type"], report.key)

    def test_preview_shows_notes_and_pdf_contains_them(self):
        url = reverse("report", args=["membros"])
        response = self.client.post(url, {
            "acao": "preview", "introduction": "Ano abençoado", "development": "Fizemos cultos",
            "conclusion": "Balanço positivo", "recommendations": "Reformar o salão"})
        for text in ("Ano abençoado", "Fizemos cultos", "Balanço positivo", "Reformar o salão"):
            self.assertContains(response, text)
        self.assertContains(response, "Pré-visualização")
        html = response.content.decode()
        self.assertLess(html.index("Fizemos cultos"), html.index("Balanço positivo"))

    def test_invalid_period_stays_on_page(self):
        url = reverse("report", args=["eventos"])
        response = self.client.post(url, {"acao": "pdf", "date_from": "2026-05-02", "date_to": "2026-05-01"})
        self.assertEqual(response["Content-Type"].split(";")[0], "text/html")
        self.assertContains(response, "não pode ser depois")

    def test_permissions_and_login(self):
        url = reverse("report", args=["financeiro"])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        common = get_user_model().objects.create_user("comum", password="senha-Forte-123")
        self.client.force_login(common)
        self.assertEqual(self.client.get(url).status_code, 403)
        hub = self.client.get(reverse("report-hub"))
        self.assertNotContains(hub, "Prestação de contas")

    def test_hub_lists_each_department(self):
        hub = self.client.get(reverse("report-hub"))
        self.assertContains(hub, "Louvor")
        self.assertContains(hub, reverse("report-scoped", args=["ministerio", self.dept.pk]))

    def test_unknown_report_redirects(self):
        self.assertEqual(self.client.get(reverse("report", args=["nada"])).status_code, 302)

    def test_html_in_notes_is_escaped_in_preview(self):
        url = reverse("report", args=["membros"])
        response = self.client.post(url, {"acao": "preview", "conclusion": "<script>alert(1)</script>"})
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_draft_finalize_reopen_flow(self):
        url = reverse("report", args=["membros"])
        data = {"introduction": "Intro", "conclusion": "Fim", "signer_name": "Pr. João", "signer_role": "Pastor"}
        response = self.client.post(url, {**data, "acao": "save"})
        saved = SavedReport.objects.get()
        self.assertRedirects(response, reverse("report-saved", args=[saved.pk]))
        self.assertEqual(saved.status, "draft")
        self.assertContains(self.client.get(reverse("report-saved", args=[saved.pk])), "Intro")

        saved_url = reverse("report-saved", args=[saved.pk])
        self.client.post(saved_url, {**data, "introduction": "Intro 2", "acao": "finalize"})
        saved.refresh_from_db()
        self.assertEqual(saved.status, "final")
        self.assertEqual(saved.finalized_on, timezone.localdate())
        self.assertEqual(saved.introduction, "Intro 2")

        self.client.post(saved_url, {**data, "introduction": "Alterado", "acao": "save"})
        saved.refresh_from_db()
        self.assertEqual(saved.introduction, "Intro 2")
        response = self.client.post(saved_url, {"acao": "pdf"})
        self.assertEqual(response["Content-Type"], "application/pdf")
        response = self.client.post(saved_url, {"acao": "csv"})
        body = response.content.decode("utf-8-sig")
        self.assertIn("Magé,", body)
        self.assertIn("Pr. João", body)
        self.assertIn("Pastor", body)

        self.client.post(saved_url, {"acao": "reopen"})
        saved.refresh_from_db()
        self.assertEqual((saved.status, saved.finalized_on), ("draft", None))

    def test_finalize_requires_signer_name(self):
        url = reverse("report", args=["membros"])
        response = self.client.post(url, {"acao": "finalize", "introduction": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SavedReport.objects.exists())

    def test_scoped_default_role_and_privacy(self):
        self.admin.first_name, self.admin.last_name = "Ana", "Lima"
        self.admin.save()
        url = reverse("report-scoped", args=["ministerio", self.dept.pk])
        self.assertContains(self.client.get(url), "Líder do ministério Louvor")
        self.client.post(reverse("report", args=["membros"]), {"acao": "save", "signer_name": "A"})
        saved = SavedReport.objects.get()
        other = get_user_model().objects.create_user("outro", password="senha-Forte-123")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("report-saved", args=[saved.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse("report-saved-list")), "Membros")

    def test_saved_list_and_delete(self):
        self.client.post(reverse("report", args=["membros"]), {"acao": "save", "signer_name": "A"})
        saved = SavedReport.objects.get()
        self.assertContains(self.client.get(reverse("report-saved-list")), "Rascunho")
        self.client.post(reverse("report-saved", args=[saved.pk]), {"acao": "delete"})
        self.assertFalse(SavedReport.objects.exists())
