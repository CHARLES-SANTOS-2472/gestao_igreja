from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import MessageOccasion


class OccasionTests(TestCase):
    def make_user(self, username, codenames):
        user = get_user_model().objects.create_user(username=username, password="senha-de-teste-123")
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        return user

    def test_default_occasions_are_seeded(self):
        names = set(MessageOccasion.objects.values_list("name", flat=True))
        for expected in ("Dia das Mães", "Dia dos Pais", "Dia do Pastor", "Natal", "Ano Novo"):
            self.assertIn(expected, names)

    def test_movable_dates(self):
        mothers = MessageOccasion.objects.get(name="Dia das Mães")
        self.assertTrue(mothers.occurs_on(date(2026, 5, 10)))
        self.assertFalse(mothers.occurs_on(date(2026, 5, 3)))
        self.assertFalse(mothers.occurs_on(date(2026, 5, 11)))
        fathers = MessageOccasion.objects.get(name="Dia dos Pais")
        self.assertTrue(fathers.occurs_on(date(2026, 8, 9)))
        self.assertEqual(str(mothers), "Dia das Mães (2º domingo de maio)")

    def test_fixed_date(self):
        christmas = MessageOccasion.objects.get(name="Natal")
        self.assertTrue(christmas.occurs_on(date(2026, 12, 25)))
        self.assertFalse(christmas.occurs_on(date(2026, 12, 24)))

    def test_requires_day_or_sunday(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            MessageOccasion(name="X", month=3).full_clean()
        with self.assertRaises(ValidationError):
            MessageOccasion(name="X", month=3, day=3, nth_sunday=1).full_clean()

    def test_user_can_register_new_occasion(self):
        self.client.force_login(self.make_user("sec", ("view_messageoccasion", "add_messageoccasion")))
        page = self.client.get(reverse("occasion-list"))
        self.assertContains(page, "Dia das Mães")
        self.assertContains(page, "Nova ocasião")
        response = self.client.post(
            reverse("occasion-create"),
            {"name": "Dia do Músico", "month": 11, "day": 22, "active": "on"},
        )
        self.assertRedirects(response, reverse("occasion-list"))
        self.assertTrue(MessageOccasion.objects.filter(name="Dia do Músico", day=22).exists())

    def test_requires_permission(self):
        self.client.force_login(self.make_user("leitor", ("view_member",)))
        self.assertEqual(self.client.get(reverse("occasion-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("occasion-create")).status_code, 403)

    def test_delete_requires_permission_and_post(self):
        occasion = MessageOccasion.objects.get(name="Natal")
        self.client.force_login(self.make_user("sec", ("view_messageoccasion",)))
        self.assertEqual(self.client.post(reverse("occasion-delete", args=[occasion.pk])).status_code, 403)
        self.client.force_login(self.make_user("adm", ("view_messageoccasion", "delete_messageoccasion")))
        self.assertEqual(self.client.get(reverse("occasion-delete", args=[occasion.pk])).status_code, 405)
        self.client.post(reverse("occasion-delete", args=[occasion.pk]))
        self.assertFalse(MessageOccasion.objects.filter(pk=occasion.pk).exists())
