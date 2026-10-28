from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone

from assistencia_social.models import AssistedFamily
from eventos.models import ChurchEvent, SpaceReservation
from financeiro.models import DonationRecord, FinancialTransaction
from ministerios.models import Department
from patrimonio.models import AdministrativeTask, ChurchAsset

from .models import Member

MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _month_starts(count, forward=False):
    today = timezone.localdate()
    index = today.year * 12 + today.month - 1
    first = index if forward else index - (count - 1)
    return [date((first + i) // 12, (first + i) % 12 + 1, 1) for i in range(count)]


def _bars(rows):
    top = max((row["value"] for row in rows), default=0) or 1
    for row in rows:
        row["percent"] = round(row["value"] * 100 / top) if row["value"] else 0
    return rows


PALETTE = ("#2f7d6b", "#d0a64f", "#5fb3a1", "#8a6d3b", "#9fd3c5", "#e3cd98")


def _with_colors(rows):
    for index, row in enumerate(rows):
        row["color"] = PALETTE[index % len(PALETTE)]
    return rows


def _pct(part, total):
    return round(part * 100 / total) if total else 0


def _donut(rows):
    # Segmentos em um círculo de perímetro 100 (pathLength), com pequena folga entre fatias.
    _with_colors(rows)
    total = sum(row["value"] for row in rows)
    filled = sum(1 for row in rows if row["value"])
    gap = 0.8 if filled > 1 else 0
    start = 0.0
    segments = []
    for row in rows:
        share = row["value"] * 100 / total if total else 0
        row["pct"] = round(share)
        if row["value"]:
            dash = round(max(share - gap, 0.3), 2)
            segments.append(
                {**row, "dash": dash, "rest": round(100 - dash, 2), "offset": round(-start, 2)}
            )
            start += share
    return segments


def _by_choice(queryset, field, choices, url, only=None):
    counts = {
        item[field]: item["total"]
        for item in queryset.values(field).annotate(total=Count("pk"))
    }
    rows = [
        {"label": label, "value": counts.get(value, 0), "url": url}
        for value, label in choices
        if only is None or value in only
    ]
    return _bars(rows)


def _columns(months, series, money=False):
    top = max((v for s in series for v in s["values"]), default=0) or 1
    groups = []
    for position, month in enumerate(months):
        bars = []
        for s in series:
            value = s["values"][position]
            bars.append(
                {
                    "css": s["css"],
                    "name": s["name"],
                    "value": value,
                    "percent": max(round(value * 100 / top), 3) if value else 0,
                }
            )
        groups.append({"label": f"{MONTHS[month.month - 1]}/{str(month.year)[2:]}", "bars": bars})
    return {"groups": groups, "legend": [{"css": s["css"], "name": s["name"]} for s in series], "money": money}


def build_charts(user):
    charts = []

    if user.has_perm("membros.view_member"):
        people = Member.objects.filter(is_placeholder=False, is_deceased=False)
        S = Member.Status
        rows = _by_choice(
            people,
            "status",
            S.choices,
            reverse("member-list"),
            only=(S.MEMBER, S.CONGREGANT, S.VISITOR, S.NEW_CONVERT, S.TRANSFERRED, S.INACTIVE),
        )
        for row in rows:
            if row["label"] in (S.VISITOR.label, S.NEW_CONVERT.label):
                row["url"] = reverse("visitor-list")
        charts.append(
            {
                "code": "ME",
                "title": "Pessoas",
                "subtitle": "Membros, congregados e visitantes",
                "kind": "donut",
                "rows": rows,
                "segments": _donut(rows),
                "total": sum(r["value"] for r in rows),
                "total_label": "cadastros",
                "url": reverse("member-list"),
                "button": "Abrir cadastro de pessoas",
            }
        )

    if user.has_perm("eventos.view_churchevent"):
        months = _month_starts(6, forward=True)
        end = date(months[-1].year + (months[-1].month // 12), months[-1].month % 12 + 1, 1)
        events = ChurchEvent.objects.filter(
            status=ChurchEvent.Status.PUBLISHED,
            starts_at__date__gte=months[0],
            starts_at__date__lt=end,
        )
        per_month = {
            (row["m"].year, row["m"].month): row["total"]
            for row in events.annotate(m=TruncMonth("starts_at")).values("m").annotate(total=Count("pk"))
        }
        values = [per_month.get((m.year, m.month), 0) for m in months]
        charts.append(
            {
                "code": "AG",
                "title": "Agenda",
                "subtitle": "Eventos publicados nos próximos 6 meses",
                "kind": "columns",
                "chart": _columns(months, [{"name": "Eventos", "css": "bar-green", "values": values}]),
                "total": sum(values),
                "total_label": "eventos",
                "url": reverse("event-list"),
                "button": "Abrir agenda",
            }
        )

    if user.has_perm("eventos.view_spacereservation"):
        rows = _by_choice(
            SpaceReservation.objects.filter(starts_at__gte=timezone.now()),
            "status",
            SpaceReservation.Status.choices,
            reverse("reservation-list"),
        )
        charts.append(
            {
                "code": "RE",
                "title": "Reservas de espaços",
                "subtitle": "Reservas futuras por situação",
                "kind": "gauge",
                "rows": _with_colors(rows),
                "pct": _pct(
                    next((r["value"] for r in rows if r["label"] == SpaceReservation.Status.RESERVED.label), 0),
                    sum(r["value"] for r in rows),
                ),
                "gauge_caption": "confirmadas",
                "total": sum(r["value"] for r in rows),
                "total_label": "reservas",
                "url": reverse("reservation-list"),
                "button": "Abrir reservas",
            }
        )

    if user.has_perm("ministerios.view_department"):
        departments = (
            Department.objects.filter(active=True)
            .annotate(total=Count("memberships"))
            .order_by("-total", "name")[:6]
        )
        rows = _bars(
            [
                {"label": d.name, "value": d.total, "url": reverse("department-detail", args=[d.pk])}
                for d in departments
            ]
        )
        charts.append(
            {
                "code": "MI",
                "title": "Ministérios",
                "subtitle": "Pessoas por departamento (maiores)",
                "kind": "bars",
                "rows": rows,
                "total": Department.objects.filter(active=True).count(),
                "total_label": "departamentos",
                "url": reverse("department-list"),
                "button": "Abrir ministérios",
            }
        )

    if user.has_perm("financeiro.view_financialtransaction"):
        months = _month_starts(6)
        settled = FinancialTransaction.objects.filter(
            status=FinancialTransaction.Status.SETTLED, settled_on__gte=months[0]
        )
        totals = {
            (row["m"].year, row["m"].month, row["kind"]): row["total"]
            for row in settled.annotate(m=TruncMonth("settled_on"))
            .values("m", "kind")
            .annotate(total=Sum("amount"))
        }

        def series(kind):
            return [float(totals.get((m.year, m.month, kind), Decimal("0"))) for m in months]

        income, expense = series(FinancialTransaction.Kind.INCOME), series(FinancialTransaction.Kind.EXPENSE)
        charts.append(
            {
                "code": "FI",
                "title": "Financeiro",
                "subtitle": "Receitas e despesas quitadas, últimos 6 meses",
                "kind": "columns",
                "chart": _columns(
                    months,
                    [
                        {"name": "Receitas", "css": "bar-green", "values": income},
                        {"name": "Despesas", "css": "bar-gold", "values": expense},
                    ],
                    money=True,
                ),
                "total": FinancialTransaction.objects.filter(
                    status=FinancialTransaction.Status.PENDING
                ).count(),
                "total_label": "lançamentos pendentes",
                "url": reverse("financial-dashboard"),
                "button": "Abrir financeiro",
            }
        )

    if user.has_perm("financeiro.view_financialtransaction"):
        months = _month_starts(6)
        giving = FinancialTransaction.objects.filter(
            kind=FinancialTransaction.Kind.INCOME,
            status=FinancialTransaction.Status.SETTLED,
            category__name__in=["Dízimos", "Ofertas"],
            settled_on__gte=months[0],
        )
        giving_totals = {
            (row["m"].year, row["m"].month, row["category__name"]): row["total"]
            for row in giving.annotate(m=TruncMonth("settled_on"))
            .values("m", "category__name")
            .annotate(total=Sum("amount"))
        }

        def giving_series(name):
            return [float(giving_totals.get((m.year, m.month, name), Decimal("0"))) for m in months]

        tithes, offerings = giving_series("Dízimos"), giving_series("Ofertas")
        charts.append(
            {
                "code": "DZ",
                "title": "Dízimos e ofertas",
                "subtitle": "Valores recebidos, últimos 6 meses",
                "kind": "columns",
                "chart": _columns(
                    months,
                    [
                        {"name": "Dízimos", "css": "bar-green", "values": tithes},
                        {"name": "Ofertas", "css": "bar-gold", "values": offerings},
                    ],
                    money=True,
                ),
                "total": f"R$ {sum(tithes) + sum(offerings):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "total_label": "no período",
                "url": reverse("financial-transaction-list"),
                "button": "Ver lançamentos",
            }
        )

    if user.has_perm("financeiro.view_donationrecord"):
        months = _month_starts(6)
        received = DonationRecord.objects.filter(
            status=DonationRecord.Status.RECEIVED, received_on__gte=months[0]
        )
        per_month = {
            (row["m"].year, row["m"].month): row["total"]
            for row in received.annotate(m=TruncMonth("received_on")).values("m").annotate(total=Count("pk"))
        }
        values = [per_month.get((m.year, m.month), 0) for m in months]
        charts.append(
            {
                "code": "DO",
                "title": "Doações",
                "subtitle": "Registros recebidos por mês",
                "kind": "columns",
                "chart": _columns(months, [{"name": "Doações", "css": "bar-gold", "values": values}]),
                "total": DonationRecord.objects.filter(status=DonationRecord.Status.RECEIVED).count(),
                "total_label": "registros recebidos",
                "url": reverse("donation-list"),
                "button": "Abrir doações",
            }
        )

    if user.has_perm("patrimonio.view_churchasset"):
        rows = _by_choice(
            ChurchAsset.objects.all(), "status", ChurchAsset.Status.choices, reverse("asset-list")
        )
        charts.append(
            {
                "code": "PA",
                "title": "Patrimônio",
                "subtitle": "Bens por situação",
                "kind": "donut",
                "rows": rows,
                "segments": _donut(rows),
                "total": sum(r["value"] for r in rows),
                "total_label": "bens",
                "url": reverse("asset-list"),
                "button": "Abrir patrimônio",
            }
        )

    if user.has_perm("patrimonio.view_administrativetask"):
        rows = _by_choice(
            AdministrativeTask.objects.all(),
            "status",
            AdministrativeTask.Status.choices,
            reverse("task-list"),
        )
        charts.append(
            {
                "code": "TA",
                "title": "Tarefas",
                "subtitle": "Demandas por situação",
                "kind": "ring",
                "rows": _with_colors(rows),
                "pct": _pct(
                    next((r["value"] for r in rows if r["label"] == AdministrativeTask.Status.COMPLETED.label), 0),
                    sum(r["value"] for r in rows),
                ),
                "gauge_caption": "concluídas",
                "total": sum(r["value"] for r in rows),
                "total_label": "tarefas",
                "url": reverse("task-list"),
                "button": "Abrir tarefas",
            }
        )

    if user.has_perm("assistencia_social.view_assistedfamily"):
        families = AssistedFamily.objects.all()
        rows = _bars(
            [
                {"label": "Em acompanhamento", "value": families.filter(active=True).count(), "url": reverse("assisted-family-list")},
                {"label": "Encerradas", "value": families.filter(active=False).count(), "url": reverse("assisted-family-list")},
            ]
        )
        charts.append(
            {
                "code": "AS",
                "title": "Assistência social",
                "subtitle": "Famílias atendidas",
                "kind": "gauge",
                "rows": _with_colors(rows),
                "pct": _pct(rows[0]["value"], sum(r["value"] for r in rows)),
                "gauge_caption": "em acompanhamento",
                "total": sum(r["value"] for r in rows),
                "total_label": "famílias",
                "url": reverse("assisted-family-list"),
                "button": "Abrir assistência",
            }
        )

    order = {"ME": 0, "AG": 1, "DZ": 2}
    charts.sort(key=lambda chart: order.get(chart["code"], 3))
    return charts
