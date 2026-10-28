from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import date

from .models import CboOccupation, FamilyRelationship, Member


class MemberManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="secretaria", password="senha-segura-teste"
        )
        permissions = Permission.objects.filter(
            content_type__app_label="membros",
            codename__in=("view_member", "add_member", "change_member"),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)

    def test_member_create_and_family_links(self):
        parent = Member.objects.create(first_name="Ana", last_name="Silva")
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Lucas",
                "last_name": "Silva",
                "status": Member.Status.CONGREGANT,
                "parents": [parent.pk],
                "email_consent": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        child = Member.objects.get(first_name="Lucas")
        self.assertEqual(child.parents.get(), parent)
        self.assertTrue(child.email_consent)
        self.assertEqual(FamilyRelationship.objects.count(), 1)

    def test_optional_family_names_create_independent_incomplete_profiles(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Paulo",
                "last_name": "Souza",
                "status": Member.Status.MEMBER,
                "spouse_name": "Ana Maria Souza",
                "parents_names": "João Silva\nMaria Lima\nJoão Silva",
                "children_names": "Pedro Souza\nLia Souza",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Paulo")
        spouse = member.spouse
        self.assertEqual(str(spouse), "Ana Maria Souza (cadastro incompleto)")
        self.assertTrue(spouse.is_placeholder)
        self.assertEqual(spouse.status, Member.Status.PENDING)
        self.assertEqual(
            list(member.parents.values_list("first_name", flat=True)),
            ["João", "Maria"],
        )
        self.assertEqual(
            list(member.children.values_list("first_name", flat=True)),
            ["Lia", "Pedro"],
        )
        self.assertEqual(Member.objects.filter(is_placeholder=True).count(), 5)

    def test_entering_already_selected_family_name_does_not_duplicate(self):
        parent = Member.objects.create(first_name="João", last_name="Silva")

        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Lucas",
                "status": Member.Status.MEMBER,
                "spouse": "",
                "spouse_name": "",
                "parents": [parent.pk],
                "parents_names": "  João   Silva  ",
                "children": [],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Lucas")
        self.assertEqual(member.parents.count(), 1)
        self.assertEqual(Member.objects.filter(is_placeholder=True).count(), 0)

    def test_existing_child_can_be_linked_from_parent_form(self):
        parent = Member.objects.create(first_name="Carlos")
        child = Member.objects.create(first_name="Davi")
        second_child = Member.objects.create(first_name="Ana")

        response = self.client.post(
            reverse("member-update", kwargs={"pk": parent.pk}),
            {
                "first_name": "Carlos",
                "status": Member.Status.MEMBER,
                "spouse": "",
                "spouse_name": "",
                "parents": [],
                "parents_names": "",
                "children": [child.pk, second_child.pk],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(parent.children.values_list("pk", flat=True)), {
            child.pk,
            second_child.pk,
        })

    def test_empty_repeatable_selects_can_remove_existing_family_links(self):
        parent = Member.objects.create(first_name="Teresa")
        child = Member.objects.create(first_name="Bruno")
        member = Member.objects.create(first_name="Daniel")
        member.parents.add(parent)
        member.children.add(child)

        response = self.client.post(
            reverse("member-update", kwargs={"pk": member.pk}),
            {
                "first_name": "Daniel",
                "status": Member.Status.MEMBER,
                "spouse": "",
                "spouse_name": "",
                "parents": [""],
                "parents_names": "",
                "children": [""],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(member.parents.exists())
        self.assertFalse(member.children.exists())

    def test_incomplete_family_profile_can_be_completed_later(self):
        parent = Member.objects.create(first_name="Elisa")
        child = Member.objects.create(
            first_name="Marina",
            status=Member.Status.PENDING,
            is_placeholder=True,
        )
        parent.children.add(child)

        response = self.client.post(
            reverse("member-update", kwargs={"pk": child.pk}),
            {
                "first_name": "Marina",
                "last_name": "Costa",
                "cpf": "12345678900",
                "status": Member.Status.CONGREGANT,
                "spouse": "",
                "parents": [parent.pk],
                "children": [],
                "parents_names": "",
                "children_names": "",
                "spouse_name": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        child.refresh_from_db()
        self.assertFalse(child.is_placeholder)
        self.assertEqual(child.status, Member.Status.CONGREGANT)
        self.assertEqual(child.parents.get(), parent)

    def test_member_search_matches_contact_fields(self):
        member = Member.objects.create(
            first_name="João", last_name="Santos", mobile="11987654321"
        )

        response = self.client.get(reverse("member-list"), {"q": "987654321"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(member))

    def test_member_list_separates_members_from_visitors(self):
        church_member = Member.objects.create(
            first_name="Membro", status=Member.Status.MEMBER
        )
        congregant = Member.objects.create(
            first_name="Congregado", status=Member.Status.CONGREGANT
        )
        visitor = Member.objects.create(
            first_name="Visitante", status=Member.Status.VISITOR
        )
        new_convert = Member.objects.create(
            first_name="Convertido", status=Member.Status.NEW_CONVERT
        )

        member_response = self.client.get(
            reverse("member-list"), {"group": "members"}
        )
        visitor_response = self.client.get(reverse("visitor-list"))

        self.assertSetEqual(
            set(member_response.context["members"]), {church_member, congregant}
        )
        self.assertSetEqual(
            set(visitor_response.context["members"]), {new_convert, visitor}
        )

    def test_member_lists_do_not_allow_status_filter_to_cross_categories(self):
        Member.objects.create(
            first_name="Visitante", status=Member.Status.VISITOR
        )

        members_response = self.client.get(
            reverse("member-list"),
            {"group": "members", "status": Member.Status.VISITOR},
        )
        visitor_response = self.client.get(
            reverse("visitor-list"), {"status": Member.Status.MEMBER}
        )

        self.assertEqual(list(members_response.context["members"]), [])
        self.assertEqual(list(visitor_response.context["members"]), [])

    def test_visitor_create_form_defaults_to_visitor_and_only_offers_visitor_statuses(self):
        response = self.client.get(reverse("visitor-create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["status"], Member.Status.VISITOR)
        self.assertEqual(
            list(form.fields["status"].choices),
            [
                (Member.Status.VISITOR, "Visitante"),
                (Member.Status.NEW_CONVERT, "Novo convertido"),
            ],
        )

    def test_visitor_can_be_created_from_visitor_section_as_new_convert(self):
        response = self.client.post(
            reverse("visitor-create"),
            {
                "first_name": "Lúcia",
                "status": Member.Status.NEW_CONVERT,
                "spouse": "",
                "spouse_name": "",
                "parents": [""],
                "parents_names": "",
                "children": [""],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Lúcia")
        self.assertEqual(member.status, Member.Status.NEW_CONVERT)
        self.assertContains(self.client.get(reverse("visitor-list")), "Lúcia")

    def test_visitor_can_be_promoted_to_member(self):
        visitor = Member.objects.create(
            first_name="Daniela",
            status=Member.Status.VISITOR,
            mobile="11999990000",
        )

        response = self.client.post(
            reverse("visitor-promote", kwargs={"pk": visitor.pk})
        )

        self.assertRedirects(
            response, reverse("member-detail", kwargs={"pk": visitor.pk})
        )
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Member.Status.MEMBER)
        self.assertEqual(visitor.joined_on, timezone.localdate())
        self.assertEqual(visitor.mobile, "11999990000")

    def test_promoting_new_convert_preserves_existing_join_date(self):
        joined_on = date(2025, 4, 12)
        new_convert = Member.objects.create(
            first_name="Rafael",
            status=Member.Status.NEW_CONVERT,
            joined_on=joined_on,
        )

        response = self.client.post(
            reverse("visitor-promote", kwargs={"pk": new_convert.pk})
        )

        self.assertEqual(response.status_code, 302)
        new_convert.refresh_from_db()
        self.assertEqual(new_convert.status, Member.Status.MEMBER)
        self.assertEqual(new_convert.joined_on, joined_on)

    def test_promote_action_is_not_available_for_non_visitors(self):
        member = Member.objects.create(
            first_name="Pedro", status=Member.Status.CONGREGANT
        )

        response = self.client.post(
            reverse("visitor-promote", kwargs={"pk": member.pk})
        )

        self.assertRedirects(
            response, reverse("member-detail", kwargs={"pk": member.pk})
        )
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.CONGREGANT)
        followed_response = self.client.post(
            reverse("visitor-promote", kwargs={"pk": member.pk}), follow=True
        )
        self.assertContains(
            followed_response,
            "Somente visitantes e novos convertidos podem ser transformados em membros.",
        )

    def test_visitor_list_offers_member_promotion_action(self):
        visitor = Member.objects.create(
            first_name="Priscila", status=Member.Status.VISITOR
        )

        response = self.client.get(reverse("visitor-list"))

        self.assertContains(response, "Tornar membro")
        self.assertContains(
            response, reverse("visitor-promote", kwargs={"pk": visitor.pk})
        )

    def test_promote_action_requires_member_change_permission(self):
        user = get_user_model().objects.create_user(username="somente_leitura")
        view_permission = Permission.objects.get(
            content_type__app_label="membros", codename="view_member"
        )
        user.user_permissions.add(view_permission)
        visitor = Member.objects.create(
            first_name="Carla", status=Member.Status.VISITOR
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("visitor-promote", kwargs={"pk": visitor.pk})
        )

        self.assertEqual(response.status_code, 403)
        visitor.refresh_from_db()
        self.assertEqual(visitor.status, Member.Status.VISITOR)

    def test_member_form_includes_cep_lookup_accessibly(self):
        response = self.client.get(reverse("member-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cep-status"')
        self.assertContains(response, "Digite o CEP para preencher o endereço automaticamente.")
        self.assertContains(response, "/static/js/cep.js")

    def test_member_form_offers_optional_family_names_and_existing_links(self):
        response = self.client.get(reverse("member-create"))

        self.assertEqual(response.status_code, 200)
        for label in (
            "Nome do cônjuge",
            "Nome dos pais/responsáveis",
            "Nome dos filhos",
            "Selecionar cônjuge já cadastrado",
            "Selecionar pais/responsáveis já cadastrados",
            "Selecionar filhos já cadastrados",
        ):
            with self.subTest(label=label):
                self.assertContains(response, label)

    def test_cbo_search_returns_matching_occupation_by_title_and_code(self):
        occupation = CboOccupation.objects.create(
            code="252105", title="Administrador"
        )

        title_response = self.client.get(
            reverse("cbo-occupation-search"), {"q": "admin"}
        )
        code_response = self.client.get(
            reverse("cbo-occupation-search"), {"q": "252105"}
        )

        self.assertEqual(title_response.status_code, 200)
        self.assertEqual(
            title_response.json()["results"],
            [{"code": occupation.code, "title": occupation.title}],
        )
        self.assertEqual(
            code_response.json()["results"],
            [{"code": occupation.code, "title": occupation.title}],
        )

    def test_official_cbo_import_is_idempotent(self):
        call_command("importar_cbo", stdout=StringIO())
        first_count = CboOccupation.objects.count()
        call_command("importar_cbo", stdout=StringIO())

        self.assertEqual(first_count, 2694)
        self.assertEqual(CboOccupation.objects.count(), first_count)
        self.assertEqual(
            CboOccupation.objects.get(pk="252105").title,
            "Administrador",
        )

    def test_cbo_search_requires_member_permission(self):
        user = get_user_model().objects.create_user(username="consulta-sem-permissao")
        self.client.force_login(user)

        response = self.client.get(reverse("cbo-occupation-search"), {"q": "admin"})

        self.assertEqual(response.status_code, 403)

    def test_member_can_save_selected_cbo_occupation(self):
        occupation = CboOccupation.objects.create(
            code="252105", title="Administrador"
        )
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Patricia",
                "status": Member.Status.MEMBER,
                "occupation_search": str(occupation),
                "occupation_code": occupation.code,
                "profession": "",
                "spouse": "",
                "spouse_name": "",
                "parents": [""],
                "parents_names": "",
                "children": [""],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Patricia")
        self.assertEqual(member.cbo_occupation, occupation)
        detail_response = self.client.get(
            reverse("member-detail", kwargs={"pk": member.pk})
        )
        self.assertContains(detail_response, "Administrador")
        self.assertContains(detail_response, "252105")

    def test_cbo_occupation_and_other_profession_cannot_conflict(self):
        occupation = CboOccupation.objects.create(
            code="252105", title="Administrador"
        )
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Renata",
                "status": Member.Status.MEMBER,
                "occupation_search": str(occupation),
                "occupation_code": occupation.code,
                "profession": "Profissão antiga",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("profession", response.context["form"].errors)
        self.assertFalse(Member.objects.filter(first_name="Renata").exists())

    def test_unknown_cbo_code_is_rejected(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Marcos",
                "status": Member.Status.MEMBER,
                "occupation_search": "999999 — Ocupação inexistente",
                "occupation_code": "999999",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("occupation_search", response.context["form"].errors)
        self.assertFalse(Member.objects.filter(first_name="Marcos").exists())

    def test_member_can_keep_profession_outside_cbo_catalog(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Rogério",
                "status": Member.Status.MEMBER,
                "occupation_search": "",
                "occupation_code": "",
                "profession": "Artesão de instrumentos",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Rogério")
        self.assertEqual(member.profession, "Artesão de instrumentos")
        self.assertIsNone(member.cbo_occupation)

    def test_edit_preserves_saved_cbo_occupation_when_field_is_omitted(self):
        occupation = CboOccupation.objects.create(
            code="252105", title="Administrador"
        )
        member = Member.objects.create(
            first_name="Claudia", cbo_occupation=occupation
        )

        response = self.client.post(
            reverse("member-update", kwargs={"pk": member.pk}),
            {"first_name": "Claudia", "status": Member.Status.MEMBER},
        )

        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.cbo_occupation, occupation)

    def test_member_date_fields_render_and_accept_brazilian_format(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Helena",
                "status": Member.Status.MEMBER,
                "birth_date": "09/02/1980",
                "joined_on": "01/03/2020",
                "baptized_on": "02/03/2020",
                "spouse": "",
                "spouse_name": "",
                "parents": [""],
                "parents_names": "",
                "children": [""],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Helena")
        self.assertEqual(member.birth_date, date(1980, 2, 9))
        self.assertEqual(member.joined_on, date(2020, 3, 1))
        self.assertEqual(member.baptized_on, date(2020, 3, 2))
        edit_response = self.client.get(
            reverse("member-update", kwargs={"pk": member.pk})
        )
        self.assertContains(edit_response, 'value="09/02/1980"')
        self.assertContains(edit_response, 'value="01/03/2020"')
        self.assertContains(edit_response, 'value="02/03/2020"')

    def test_edit_preserves_saved_data_when_fields_are_not_submitted(self):
        spouse = Member.objects.create(first_name="Lia")
        parent = Member.objects.create(first_name="Roberto")
        child = Member.objects.create(first_name="Caio")
        member = Member.objects.create(
            first_name="Sofia",
            birth_date=date(1990, 4, 5),
            joined_on=date(2018, 6, 7),
            baptized_on=date(2019, 8, 9),
            spouse=spouse,
        )
        member.parents.add(parent)
        member.children.add(child)

        response = self.client.post(
            reverse("member-update", kwargs={"pk": member.pk}),
            {
                "first_name": "Sofia",
                "status": Member.Status.MEMBER,
            },
        )

        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.birth_date, date(1990, 4, 5))
        self.assertEqual(member.joined_on, date(2018, 6, 7))
        self.assertEqual(member.baptized_on, date(2019, 8, 9))
        self.assertEqual(member.spouse, spouse)
        self.assertEqual(member.parents.get(), parent)
        self.assertEqual(member.children.get(), child)

    def test_family_selection_uses_one_select_per_person(self):
        parent = Member.objects.create(first_name="Marcos")
        child = Member.objects.create(first_name="Joana")
        member = Member.objects.create(first_name="Mateus")
        member.parents.add(parent)
        member.children.add(child)

        response = self.client.get(reverse("member-update", kwargs={"pk": member.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-repeatable-select')
        self.assertContains(response, 'data-add-select')
        self.assertContains(response, "Adicionar outro")
        self.assertContains(response, "/static/js/member-form.js")

    def test_spouse_selector_has_explicit_none_option(self):
        response = self.client.get(reverse("member-create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].fields["spouse"].empty_label,
            "Nenhum",
        )

    def test_deceased_member_can_be_saved_with_optional_date(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Ester",
                "status": Member.Status.MEMBER,
                "is_deceased": "on",
                "deceased_on": "14/09/2022",
                "spouse": "",
                "spouse_name": "",
                "parents": [""],
                "parents_names": "",
                "children": [""],
                "children_names": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(first_name="Ester")
        self.assertTrue(member.is_deceased)
        self.assertEqual(member.deceased_on, date(2022, 9, 14))
        self.assertContains(
            self.client.get(reverse("member-detail", kwargs={"pk": member.pk})),
            "In memoriam",
        )

    def test_deceased_date_requires_in_memoriam_checkbox(self):
        response = self.client.post(
            reverse("member-create"),
            {
                "first_name": "Noemi",
                "status": Member.Status.MEMBER,
                "deceased_on": "14/09/2022",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("deceased_on", response.context["form"].errors)

    def test_member_pages_require_login(self):
        self.client.logout()

        response = self.client.get(reverse("member-list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_user_without_member_permission_cannot_access_member_data(self):
        user = get_user_model().objects.create_user(username="visitante")
        self.client.force_login(user)

        for url in (reverse("dashboard"), reverse("member-list")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_dashboard_shows_charts_without_recent_member_records(self):
        Member.objects.create(first_name="Pessoa Reservada")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visão geral da igreja")
        self.assertContains(response, "Abrir cadastro de pessoas")
        self.assertContains(response, reverse("member-list"))
        self.assertContains(response, "Mensagem da igreja")
        self.assertContains(response, "Imagem da igreja")
        self.assertNotContains(response, "Cadastros recentes")
        self.assertNotContains(response, "Pessoa Reservada")

    def test_dashboard_renders_every_chart_for_superuser(self):
        admin = get_user_model().objects.create_superuser("root", "r@x.com", "SenhaForte#2026")
        self.client.force_login(admin)
        Member.objects.create(first_name="Ana", status=Member.Status.MEMBER)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["charts"]), 9)
        for label in ("Abrir agenda", "Abrir financeiro", "Abrir doações", "Abrir patrimônio", "Abrir assistência"):
            self.assertContains(response, label)

    def test_dashboard_shows_only_modules_available_to_the_user(self):
        user = get_user_model().objects.create_user(username="tesoureiro")
        finance_permission = Permission.objects.get(
            content_type__app_label="financeiro",
            codename="view_financialtransaction",
        )
        user.user_permissions.add(finance_permission)
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Abrir financeiro")
        self.assertNotContains(response, "Abrir cadastro de pessoas")
        self.assertNotContains(response, "Abrir doações")

    def test_member_form_prevents_self_as_spouse(self):
        member = Member.objects.create(first_name="Bia")

        response = self.client.post(
            reverse("member-update", kwargs={"pk": member.pk}),
            {
                "first_name": "Bia",
                "status": Member.Status.MEMBER,
                "spouse": member.pk,
                "parents": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("spouse", response.context["form"].errors)

    def test_spouse_link_is_shared_and_can_be_removed(self):
        ana = Member.objects.create(first_name="Ana")
        bia = Member.objects.create(first_name="Bia")

        self.client.post(
            reverse("member-update", kwargs={"pk": ana.pk}),
            {
                "first_name": "Ana",
                "status": Member.Status.MEMBER,
                "spouse": bia.pk,
                "parents": [],
            },
        )
        ana.refresh_from_db()
        bia.refresh_from_db()
        self.assertEqual(ana.spouse, bia)

        self.client.post(
            reverse("member-update", kwargs={"pk": bia.pk}),
            {
                "first_name": "Bia",
                "status": Member.Status.MEMBER,
                "spouse": "",
                "parents": [],
            },
        )
        ana.refresh_from_db()
        self.assertIsNone(ana.spouse)
