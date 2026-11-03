"""Catálogo de relatórios: cada item sabe montar suas tabelas a partir dos dados do sistema."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone


@dataclass
class Section:
    title: str
    header: list
    rows: list
    right: tuple = ()  # colunas alinhadas à direita (valores)


@dataclass
class ReportData:
    subtitle: str = ""
    summary: list = field(default_factory=list)  # [(rótulo, valor)]
    sections: list = field(default_factory=list)


@dataclass
class ReportDef:
    key: str
    title: str
    module: str
    description: str
    permission: str
    build: Callable
    period: Optional[str] = None  # None, "mes" (mês inteiro) ou "ate_hoje" (do dia 1 até hoje)
    scoped: bool = False  # relatório de um item específico (ex.: um ministério)


def money(value):
    value = Decimal(value or 0)
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def day(value):
    return f"{value:%d/%m/%Y}" if value else "—"


def when(value):
    return f"{timezone.localtime(value):%d/%m/%Y %H:%M}" if value else "—"


def yes(value):
    return "Sim" if value else "Não"


def default_period(kind):
    today = timezone.localdate()
    first = today.replace(day=1)
    if kind == "mes":
        nxt = (first + timedelta(days=32)).replace(day=1)
        return first, nxt - timedelta(days=1)
    return first, today


def period_text(date_from, date_to):
    return f"Período: {day(date_from)} a {day(date_to)}."


# ---------------------------------------------------------------- membros
def _members(statuses, title):
    from membros.models import Member

    def build(params):
        queryset = Member.objects.filter(status__in=statuses, is_deceased=False).order_by(
            "first_name", "last_name"
        )
        rows = [
            [str(m), m.get_status_display(), m.mobile or m.landline or "—",
             f"{m.city}/{m.state}" if m.city else "—", day(m.joined_on)]
            for m in queryset
        ]
        counts = {}
        for m in queryset:
            counts[m.get_status_display()] = counts.get(m.get_status_display(), 0) + 1
        return ReportData(
            subtitle=title,
            summary=[("Total", len(rows))] + list(counts.items()),
            sections=[Section("Relação", ["Nome", "Situação", "Telefone", "Cidade", "Entrada"], rows)],
        )

    return build


def _members_build(params):
    from membros.models import Member

    S = Member.Status
    return _members([S.MEMBER, S.CONGREGANT, S.TRANSFERRED, S.INACTIVE], "Membros e congregados")(params)


def _visitors_build(params):
    from membros.models import Member

    S = Member.Status
    return _members([S.VISITOR, S.NEW_CONVERT], "Visitantes e novos convertidos")(params)


def _birthdays_build(params):
    from membros.models import Member

    month = params["date_from"].month
    people = Member.objects.filter(birth_date__month=month, is_deceased=False).exclude(
        status=Member.Status.INACTIVE
    ).order_by("birth_date__day", "first_name")
    rows = [[f"{m.birth_date:%d/%m}", str(m), m.get_status_display(), m.mobile or "—"] for m in people]
    return ReportData(
        subtitle=f"Aniversariantes do mês {month:02d}",
        summary=[("Aniversariantes", len(rows))],
        sections=[Section("Aniversariantes", ["Dia", "Nome", "Situação", "Telefone"], rows)],
    )


# ----------------------------------------------------------------- agenda
def _events_build(params):
    from eventos.models import ChurchEvent

    events = ChurchEvent.objects.filter(
        starts_at__date__gte=params["date_from"], starts_at__date__lte=params["date_to"]
    ).annotate(
        registered=Count("registrations", distinct=True),
        present=Count("registrations", filter=Q(registrations__attended=True), distinct=True),
    ).order_by("starts_at")
    rows = [[when(e.starts_at), e.title, e.get_kind_display(), e.get_status_display(),
             e.location or "—", e.registered, e.present] for e in events]
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"]),
        summary=[("Eventos", len(rows)), ("Inscritos", sum(r[5] for r in rows)),
                 ("Presenças", sum(r[6] for r in rows))],
        sections=[Section("Eventos", ["Data", "Evento", "Tipo", "Situação", "Local", "Inscritos", "Presentes"],
                          rows, (5, 6))],
    )


def _reservations_build(params):
    from eventos.models import SpaceReservation

    items = SpaceReservation.objects.filter(
        starts_at__date__gte=params["date_from"], starts_at__date__lte=params["date_to"]
    ).select_related("space").order_by("starts_at")
    rows = [[when(r.starts_at), str(r.space), r.purpose, r.get_status_display()] for r in items]
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"]),
        summary=[("Reservas", len(rows))],
        sections=[Section("Reservas de espaços", ["Início", "Espaço", "Finalidade", "Situação"], rows)],
    )


# ------------------------------------------------------------- ministérios
def _departments_build(params):
    from ministerios.models import Department

    departments = Department.objects.annotate(
        people=Count("memberships", distinct=True),
        acts=Count(
            "activities",
            filter=Q(activities__starts_at__date__gte=params["date_from"],
                     activities__starts_at__date__lte=params["date_to"]),
            distinct=True,
        ),
    ).select_related("leader", "vice_leader").order_by("name")
    rows = [[d.name, str(d.leader) if d.leader else "—", str(d.vice_leader) if d.vice_leader else "—",
             "Ativo" if d.active else "Inativo", d.people, d.acts] for d in departments]
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"]),
        summary=[("Ministérios", len(rows)), ("Ativos", sum(1 for r in rows if r[3] == "Ativo"))],
        sections=[Section("Ministérios", ["Ministério", "Líder", "Vice-líder", "Situação", "Pessoas",
                                         "Atividades"], rows, (4, 5))],
    )


def _department_build(params, obj):
    activities = obj.activities.filter(
        starts_at__date__gte=params["date_from"], starts_at__date__lte=params["date_to"]
    ).order_by("starts_at")
    members = obj.memberships.select_related("member").order_by("member__first_name")
    act_rows = []
    present = absent = 0
    for a in activities:
        records = list(a.attendance_records.all())
        p = sum(1 for r in records if r.status == "present")
        present += p
        absent += len(records) - p
        act_rows.append([when(a.starts_at), a.title, a.get_kind_display(), a.get_status_display(),
                         a.location or "—", p])
    summary = [("Participantes", members.count()), ("Atividades no período", len(act_rows)),
               ("Presenças registradas", present)]
    if obj.leader:
        summary.insert(0, ("Líder", str(obj.leader)))
    return ReportData(
        subtitle=f"{obj.name}. {period_text(params['date_from'], params['date_to'])}",
        summary=summary,
        sections=[
            Section("Participantes", ["Nome", "Função"],
                    [[str(m.member), m.get_role_display()] for m in members]),
            Section("Atividades e reuniões",
                    ["Data", "Atividade", "Tipo", "Situação", "Local", "Presentes"], act_rows, (5,)),
        ],
    )


# --------------------------------------------------------------- financeiro
def _financial_build(params):
    from financeiro.views import financial_report_data

    d = financial_report_data(params["date_from"], params["date_to"])
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"])
        + " Somente lançamentos liquidados entram nos totais.",
        summary=[("Receitas recebidas", money(d["income_total"])),
                 ("Despesas pagas", money(d["expense_total"])), ("Saldo", money(d["net_total"]))],
        sections=[
            Section("Por categoria", ["Tipo", "Categoria", "Lançamentos", "Total"],
                    [["Receita" if r["kind"] == "income" else "Despesa", r["category__name"], r["count"],
                      money(r["total"])] for r in d["category_rows"]], (2, 3)),
            Section("Por forma de recebimento/pagamento", ["Forma", "Lançamentos", "Total"],
                    [[r["method_label"], r["count"], money(r["total"])] for r in d["payment_method_rows"]],
                    (1, 2)),
            Section("Por ministério", ["Ministério", "Receitas", "Despesas", "Saldo"],
                    [[r["department__name"] or "Sem ministério", money(r["income"]), money(r["expense"]),
                      money(r["net"])] for r in d["department_rows"]], (1, 2, 3)),
            Section("Por evento", ["Evento", "Receitas", "Despesas"],
                    [[r["event__title"] or "Sem evento", money(r["income"]), money(r["expense"])]
                     for r in d["event_rows"]], (1, 2)),
            Section("Pendências no período (fora dos totais)", ["Descrição", "Tipo", "Vencimento", "Valor"],
                    [[e.title, e.get_kind_display(), day(e.due_on), money(e.amount)]
                     for e in d["pending_transactions"]], (3,)),
        ],
    )


def _donations_build(params):
    from financeiro.models import DonationRecord

    items = DonationRecord.objects.filter(
        received_on__gte=params["date_from"], received_on__lte=params["date_to"],
        status=DonationRecord.Status.RECEIVED,
    ).order_by("received_on")
    total = items.aggregate(t=Sum("amount"))["t"]
    rows = [[day(i.received_on), "Anônima" if i.anonymous or not i.donor_name else i.donor_name,
             i.get_donation_type_display(), i.get_destination_display(),
             money(i.amount) if i.amount is not None else (i.description or "—")] for i in items]
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"]) + " Doações canceladas não entram.",
        summary=[("Doações", len(rows)), ("Total em dinheiro", money(total))],
        sections=[Section("Doações recebidas", ["Data", "Doador", "Tipo", "Destinação", "Valor/Item"], rows, (4,))],
    )


# --------------------------------------------------------------- patrimônio
def _assets_build(params):
    from patrimonio.models import ChurchAsset

    assets = ChurchAsset.objects.order_by("category", "name")
    rows = [[a.name, a.get_category_display(), a.asset_tag or "—", a.location or "—",
             a.get_status_display(), money(a.purchase_value) if a.purchase_value is not None else "—"]
            for a in assets]
    by_status = {}
    for a in assets:
        by_status[a.get_status_display()] = by_status.get(a.get_status_display(), 0) + 1
    total = assets.aggregate(t=Sum("purchase_value"))["t"]
    return ReportData(
        subtitle="Bens cadastrados",
        summary=[("Bens", len(rows)), ("Valor de aquisição", money(total))] + list(by_status.items()),
        sections=[Section("Bens", ["Bem", "Categoria", "Nº patrimonial", "Local", "Situação", "Valor"],
                          rows, (5,))],
    )


def _contracts_build(params):
    from patrimonio.models import Contract

    items = Contract.objects.select_related("supplier").order_by("end_date")
    rows = [[c.title, c.supplier.name, c.get_status_display(), day(c.start_date), day(c.end_date),
             money(c.value) if c.value is not None else "—"] for c in items]
    return ReportData(
        subtitle="Contratos e vencimentos",
        summary=[("Contratos", len(rows))],
        sections=[Section("Contratos", ["Contrato", "Fornecedor", "Situação", "Início", "Vencimento", "Valor"],
                          rows, (5,))],
    )


def _suppliers_build(params):
    from patrimonio.models import Supplier

    items = Supplier.objects.order_by("name")
    rows = [[s.name, s.contact_name or "—", s.phone or "—", "Ativo" if s.active else "Inativo"] for s in items]
    return ReportData(
        subtitle="Fornecedores cadastrados",
        summary=[("Fornecedores", len(rows))],
        sections=[Section("Fornecedores", ["Fornecedor", "Contato", "Telefone", "Situação"], rows)],
    )


def _tasks_build(params):
    from patrimonio.models import AdministrativeTask

    items = AdministrativeTask.objects.select_related("assigned_to").order_by("due_date")
    rows = [[t.title, t.get_priority_display(), t.get_status_display(), day(t.due_date),
             t.assigned_to.get_full_name() or t.assigned_to.get_username() if t.assigned_to else "—"]
            for t in items]
    return ReportData(
        subtitle="Tarefas e pendências administrativas",
        summary=[("Tarefas", len(rows))],
        sections=[Section("Tarefas", ["Tarefa", "Prioridade", "Situação", "Prazo", "Responsável"], rows)],
    )


# ------------------------------------------------------ assistência social
def _assistance_build(params):
    from assistencia_social.models import AssistanceRecord

    items = AssistanceRecord.objects.filter(
        assistance_date__gte=params["date_from"], assistance_date__lte=params["date_to"]
    ).select_related("family").order_by("assistance_date")
    by_type = {}
    for i in items:
        by_type[i.get_aid_type_display()] = by_type.get(i.get_aid_type_display(), 0) + 1
    rows = [[day(i.assistance_date), i.family.reference_name, i.get_aid_type_display(),
             i.get_status_display()] for i in items]
    return ReportData(
        subtitle=period_text(params["date_from"], params["date_to"])
        + " Relatório restrito: não inclui endereço nem telefone.",
        summary=[("Ajudas", len(rows)), ("Famílias atendidas", len({i.family_id for i in items}))],
        sections=[
            Section("Por tipo de ajuda", ["Tipo", "Quantidade"], [[k, v] for k, v in by_type.items()], (1,)),
            Section("Ajudas registradas", ["Data", "Família", "Tipo", "Situação"], rows),
        ],
    )


REPORTS = [
    ReportDef("membros", "Membros e congregados", "Membros", "Relação com situação, telefone e data de entrada.",
              "membros.view_member", _members_build),
    ReportDef("visitantes", "Visitantes e novos convertidos", "Membros",
              "Acompanhamento de quem chegou recentemente.", "membros.view_member", _visitors_build),
    ReportDef("aniversariantes", "Aniversariantes do mês", "Membros",
              "Escolha qualquer data do mês desejado.", "membros.view_member", _birthdays_build, period="mes"),
    ReportDef("eventos", "Cultos e eventos", "Agenda", "Eventos do período, com inscritos e presenças.",
              "eventos.view_churchevent", _events_build, period="mes"),
    ReportDef("reservas", "Reservas de espaços", "Agenda", "Uso de salões, templo e salas.",
              "eventos.view_spacereservation", _reservations_build, period="mes"),
    ReportDef("ministerios", "Todos os ministérios", "Ministérios",
              "Líderes, quantidade de pessoas e atividades.", "ministerios.view_department",
              _departments_build, period="mes"),
    ReportDef("ministerio", "Relatório do ministério", "Ministérios",
              "Participantes, atividades e presenças de um ministério.", "ministerios.view_department",
              _department_build, period="mes", scoped=True),
    ReportDef("financeiro", "Prestação de contas", "Financeiro",
              "Receitas, despesas, categorias, ministérios e pendências.", "financeiro.view_financialtransaction",
              _financial_build, period="ate_hoje"),
    ReportDef("doacoes", "Doações recebidas", "Financeiro", "Doações do período, sem dados bancários.",
              "financeiro.view_donationrecord", _donations_build, period="ate_hoje"),
    ReportDef("bens", "Bens patrimoniais", "Patrimônio", "Bens, localização, situação e valores.",
              "patrimonio.view_churchasset", _assets_build),
    ReportDef("contratos", "Contratos", "Patrimônio", "Vigências, vencimentos e valores.",
              "patrimonio.view_contract", _contracts_build),
    ReportDef("fornecedores", "Fornecedores", "Patrimônio", "Contatos e situação.",
              "patrimonio.view_supplier", _suppliers_build),
    ReportDef("tarefas", "Tarefas administrativas", "Patrimônio", "Pendências, prazos e responsáveis.",
              "patrimonio.view_administrativetask", _tasks_build),
    ReportDef("assistencia", "Ajudas da assistência social", "Assistência social",
              "Ajudas do período, sem endereço ou telefone.", "assistencia_social.view_assistancerecord",
              _assistance_build, period="ate_hoje"),
]
BY_KEY = {r.key: r for r in REPORTS}
