from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from membros.models import Member, MessageOccasion

from .models import MessageLog
from .services import build_banner, normalize_phone, run_daily, welcome_member


class MessagingTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(MEDIA_ROOT=tmp.name, MESSAGING_LIVE=False, OPENAI_API_KEY="")
        override.enable()
        self.addCleanup(override.disable)
        self.today = date(2026, 11, 3)
        self.member = Member.objects.create(
            first_name="Ana", birth_date=date(1990, 11, 3), mobile="(11) 91234-5678",
            email="ana@example.com", email_consent=True, whatsapp_consent=True,
            whatsapp_daily_consent=True,
        )

    def test_banner_is_png(self):
        png = build_banner("Feliz aniversário, Ana!", "Que Deus abençoe.", "Verso", "Salmos 23:1")
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("(11) 91234-5678"), "5511912345678")
        self.assertEqual(normalize_phone("123"), "")

    def test_birthday_simulated_and_idempotent(self):
        counts = run_daily(self.today)
        self.assertEqual(counts["birthday"], 2)
        self.assertEqual(MessageLog.objects.filter(status="simulated").count(), 2)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(run_daily(self.today)["birthday"], 0)
        log = MessageLog.objects.first()
        self.assertTrue((Path(__import__("django").conf.settings.MEDIA_ROOT) / log.banner).exists())

    def test_birthday_skips_daily_for_same_person(self):
        run_daily(self.today)
        self.assertFalse(MessageLog.objects.filter(kind="daily").exists())

    def test_live_email_is_sent(self):
        run_daily(self.today, live=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])

    def test_whatsapp_live_without_config_fails_and_is_logged(self):
        run_daily(self.today, live=True)
        log = MessageLog.objects.get(channel="whatsapp")
        self.assertEqual(log.status, "failed")

    def test_no_consent_no_message(self):
        Member.objects.filter(pk=self.member.pk).update(email_consent=False)
        self.member.refresh_from_db()
        Member.objects.filter(pk=self.member.pk).update(
            whatsapp_consent=False, whatsapp_daily_consent=False
        )
        self.assertEqual(run_daily(self.today)["birthday"], 0)

    def test_occasion_and_daily(self):
        other = Member.objects.create(
            first_name="Bia", mobile="11998887777", whatsapp_consent=True,
            whatsapp_daily_consent=True,
        )
        day = date(2026, 5, 10)
        MessageOccasion.objects.create(name="Dia das Mães", month=5, day=10)
        counts = run_daily(day)
        self.assertEqual(counts["occasion"], 3)
        self.assertEqual(counts["daily"], 0)
        daily = run_daily(date(2026, 6, 1))
        self.assertEqual(daily["daily"], 2)
        self.assertTrue(MessageLog.objects.filter(member=other, kind="daily").exists())

    def test_inactive_and_deceased_excluded(self):
        Member.objects.filter(pk=self.member.pk).update(is_deceased=True)
        self.assertEqual(run_daily(self.today)["birthday"], 0)

    def test_welcome_once(self):
        first = welcome_member(self.member.pk)
        self.assertEqual(len(first), 2)
        self.assertEqual(welcome_member(self.member.pk), [])

    def test_welcome_after_creation_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            Member.objects.create(first_name="Caio", email="c@example.com", email_consent=True)
        self.assertTrue(MessageLog.objects.filter(member__first_name="Caio", kind="welcome").exists())

    def test_command_dry_run(self):
        out = StringIO()
        call_command("enviar_mensagens", "--dry-run", "--date", "2026-11-03", stdout=out)
        self.assertIn("SIMULAÇÃO", out.getvalue())
