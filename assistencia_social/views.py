from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .forms import (
    AssistanceRecordFilterForm,
    AssistanceRecordForm,
    AssistedFamilyForm,
)
from .models import AssistanceRecord, AssistedFamily


REPORTLAB_FONTS = Path(reportlab_file).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("ChurchSans", str(REPORTLAB_FONTS / "Vera.ttf")))
pdfmetrics.registerFont(
    TTFont("ChurchSans-Bold", str(REPORTLAB_FONTS / "VeraBd.ttf"))
)


def get_filtered_assistance_records(params):
    queryset = AssistanceRecord.objects.select_related("family", "recorded_by")
    filter_form = AssistanceRecordFilterForm(params)
    if not filter_form.is_valid():
        return queryset.none(), filter_form

    filters = filter_form.cleaned_data
    if filters["status"]:
        queryset = queryset.filter(status=filters["status"])
    if filters["aid_type"]:
        queryset = queryset.filter(aid_type=filters["aid_type"])
    if filters["date_from"]:
        queryset = queryset.filter(assistance_date__gte=filters["date_from"])
    if filters["date_to"]:
        queryset = queryset.filter(assistance_date__lte=filters["date_to"])
    return queryset, filter_form


def report_paragraph(value, style):
    return Paragraph(escape(str(value or "—")), style)


def draw_assistance_report_page(canvas, document):
    canvas.saveState()
    page_width, page_height = A4
    left = 16 * mm
    right = page_width - 16 * mm

    canvas.setFillColor(colors.HexColor("#173b35"))
    canvas.roundRect(
        left,
        page_height - 31 * mm,
        10 * mm,
        10 * mm,
        2 * mm,
        fill=1,
        stroke=0,
    )
    canvas.setFillColor(colors.HexColor("#c49a5a"))
    canvas.setFont("ChurchSans-Bold", 13)
    canvas.drawCentredString(left + 5 * mm, page_height - 24.4 * mm, "G")

    canvas.setFillColor(colors.HexColor("#173b35"))
    canvas.setFont("ChurchSans-Bold", 14)
    canvas.drawString(left + 14 * mm, page_height - 24 * mm, "Gestão da Igreja")
    canvas.setFillColor(colors.HexColor("#71807b"))
    canvas.setFont("ChurchSans", 8)
    canvas.drawString(
        left + 14 * mm, page_height - 29 * mm, "RELATÓRIO DE ASSISTÊNCIA SOCIAL"
    )

    reserved_width = 70 * mm
    canvas.setFillColor(colors.HexColor("#f8fbf9"))
    canvas.roundRect(
        right - reserved_width,
        page_height - 33 * mm,
        reserved_width,
        19 * mm,
        2 * mm,
        fill=1,
        stroke=0,
    )
    canvas.setFillColor(colors.HexColor("#4a5d55"))
    canvas.setFont("ChurchSans-Bold", 7)
    canvas.drawString(
        right - reserved_width + 3 * mm,
        page_height - 20 * mm,
        "DADOS INSTITUCIONAIS",
    )
    canvas.setFont("ChurchSans", 6.5)
    canvas.drawString(
        right - reserved_width + 3 * mm,
        page_height - 25 * mm,
        "Nome, logotipo e contatos oficiais a configurar",
    )
    canvas.setStrokeColor(colors.HexColor("#c49a5a"))
    canvas.setLineWidth(1)
    canvas.line(left, page_height - 38 * mm, right, page_height - 38 * mm)

    canvas.setStrokeColor(colors.HexColor("#dce5e0"))
    canvas.setLineWidth(0.5)
    canvas.line(left, 14 * mm, right, 14 * mm)
    canvas.setFillColor(colors.HexColor("#71807b"))
    canvas.setFont("ChurchSans", 7)
    canvas.drawString(
        left,
        9 * mm,
    "Gestão da Igreja · Documento administrativo restrito · "
    f"Gerado em {timezone.localtime():%d/%m/%Y %H:%M}",
    )
    canvas.drawRightString(right, 9 * mm, f"Página {document.page}")
    canvas.restoreState()


def build_assistance_report_pdf(queryset, filter_form):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=43 * mm,
        bottomMargin=20 * mm,
        title="Relatório de Assistência Social",
        author="Gestão da Igreja",
    )
    styles = {
        "section": ParagraphStyle(
            "ReportSection",
            fontName="ChurchSans-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#173b35"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            fontName="ChurchSans",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#192b28"),
        ),
        "small": ParagraphStyle(
            "ReportSmall",
            fontName="ChurchSans",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#4a5d55"),
        ),
        "header": ParagraphStyle(
            "ReportTableHeader",
            fontName="ChurchSans-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.white,
        ),
        "summary_label": ParagraphStyle(
            "ReportSummaryLabel",
            fontName="ChurchSans",
            fontSize=6.5,
            leading=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4a5d55"),
        ),
        "summary_value": ParagraphStyle(
            "ReportSummaryValue",
            fontName="ChurchSans-Bold",
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#173b35"),
        ),
        "empty": ParagraphStyle(
            "ReportEmpty",
            fontName="ChurchSans",
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#71807b"),
        ),
    }
    summary = queryset.aggregate(
        total_count=Count("pk"),
        planned_count=Count(
            "pk", filter=Q(status=AssistanceRecord.Status.PLANNED)
        ),
        delivered_count=Count(
            "pk", filter=Q(status=AssistanceRecord.Status.DELIVERED)
        ),
        cancelled_count=Count(
            "pk", filter=Q(status=AssistanceRecord.Status.CANCELLED)
        ),
        delivered_financial_total=Coalesce(
            Sum(
                "amount",
                filter=Q(
                    status=AssistanceRecord.Status.DELIVERED,
                    aid_type=AssistanceRecord.AidType.FINANCIAL,
                ),
            ),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )
    story = [
        Paragraph("Resumo do período", styles["section"]),
    ]
    summary_items = (
        ("Registros", summary["total_count"]),
        ("Entregues", summary["delivered_count"]),
        ("Programadas", summary["planned_count"]),
        ("Canceladas", summary["cancelled_count"]),
        (
            "Ajuda financeira entregue",
            f"R$ {summary['delivered_financial_total']:.2f}".replace(".", ","),
        ),
    )
    summary_cells = [
        [
            Paragraph(str(value), styles["summary_value"]),
            Paragraph(label, styles["summary_label"]),
        ]
        for label, value in summary_items
    ]
    summary_table = Table(
        [summary_cells],
        colWidths=[(A4[0] - 32 * mm) / len(summary_items)] * len(summary_items),
    )
    summary_table.setStyle(
        TableStyle(
            [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f7f4")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce5e0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce5e0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 5 * mm)])

    cleaned = filter_form.cleaned_data
    filter_labels = []
    if cleaned["date_from"]:
        filter_labels.append(f"De {cleaned['date_from']:%d/%m/%Y}")
    if cleaned["date_to"]:
        filter_labels.append(f"até {cleaned['date_to']:%d/%m/%Y}")
    if cleaned["status"]:
        filter_labels.append(
            f"Situação: {dict(AssistanceRecord.Status.choices)[cleaned['status']]}"
        )
    if cleaned["aid_type"]:
        filter_labels.append(
            f"Tipo: {dict(AssistanceRecord.AidType.choices)[cleaned['aid_type']]}"
        )
    story.append(
        Paragraph(
            "Filtros: "
            + escape(", ".join(filter_labels) if filter_labels else "sem filtros"),
            styles["small"],
        )
    )

    aid_type_rows = queryset.values("aid_type").annotate(
        record_count=Count("pk"),
        delivered_count=Count(
            "pk", filter=Q(status=AssistanceRecord.Status.DELIVERED)
        ),
        delivered_quantity=Sum(
            "quantity", filter=Q(status=AssistanceRecord.Status.DELIVERED)
        ),
        delivered_amount=Coalesce(
            Sum("amount", filter=Q(status=AssistanceRecord.Status.DELIVERED)),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    ).order_by("aid_type")
    if aid_type_rows:
        story.append(Paragraph("Resumo por tipo de ajuda", styles["section"]))
        type_data = [
            [
                Paragraph("Tipo", styles["header"]),
                Paragraph("Registros", styles["header"]),
                Paragraph("Entregues", styles["header"]),
                Paragraph("Quantidade entregue", styles["header"]),
                Paragraph("Valor financeiro entregue", styles["header"]),
            ]
        ]
        type_labels = dict(AssistanceRecord.AidType.choices)
        for row in aid_type_rows:
            type_data.append(
                [
                    report_paragraph(type_labels[row["aid_type"]], styles["body"]),
                    str(row["record_count"]),
                    str(row["delivered_count"]),
                    (
                        "—"
                        if row["aid_type"] == AssistanceRecord.AidType.FINANCIAL
                        else str(row["delivered_quantity"] or 0)
                    ),
                    (
                        f"R$ {row['delivered_amount']:.2f}".replace(".", ",")
                        if row["aid_type"] == AssistanceRecord.AidType.FINANCIAL
                        else "—"
                    ),
                ]
            )
        type_table = Table(
            type_data,
            colWidths=[150, 65, 65, 100, A4[0] - 32 * mm - 380],
            repeatRows=1,
        )
        type_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b35")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fbf9")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce5e0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([type_table, Spacer(1, 4 * mm)])

    story.append(Paragraph("Registros detalhados", styles["section"]))
    records = [
        [
            Paragraph("Família", styles["header"]),
            Paragraph("Tipo", styles["header"]),
            Paragraph("Descrição", styles["header"]),
            Paragraph("Qtd. / valor", styles["header"]),
            Paragraph("Data", styles["header"]),
            Paragraph("Situação", styles["header"]),
        ]
    ]
    for record in queryset:
        value = (
            f"R$ {record.amount:.2f}".replace(".", ",")
            if record.amount is not None
            else str(record.quantity)
        )
        records.append(
            [
                report_paragraph(record.family.reference_name, styles["body"]),
                report_paragraph(record.get_aid_type_display(), styles["body"]),
                report_paragraph(record.description, styles["body"]),
                report_paragraph(value, styles["body"]),
                report_paragraph(
                    record.assistance_date.strftime("%d/%m/%Y"), styles["body"]
                ),
                report_paragraph(record.get_status_display(), styles["body"]),
            ]
        )
    if len(records) == 1:
        story.append(
            Paragraph("Nenhuma ajuda encontrada para os filtros selecionados.", styles["empty"])
        )
    else:
        records_table = Table(
            records,
            colWidths=[88, 68, 133, 72, 63, 80],
            repeatRows=1,
        )
        records_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b35")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fbf9")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce5e0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(records_table)

    document.build(
        story,
        onFirstPage=draw_assistance_report_page,
        onLaterPages=draw_assistance_report_page,
    )
    return buffer.getvalue()


class AssistedFamilyListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AssistedFamily
    template_name = "assistencia_social/family_list.html"
    context_object_name = "families"
    permission_required = "assistencia_social.view_assistedfamily"
    paginate_by = 25

    def get_queryset(self):
        queryset = AssistedFamily.objects.all()
        query = self.request.GET.get("q", "").strip()
        active = self.request.GET.get("active", "").strip()
        if query:
            queryset = queryset.filter(
                Q(reference_name__icontains=query)
                | Q(contact_name__icontains=query)
                | Q(phone__icontains=query)
                | Q(postal_code__icontains=query)
                | Q(street__icontains=query)
                | Q(neighborhood__icontains=query)
                | Q(city__icontains=query)
                | Q(state__icontains=query)
                | Q(address__icontains=query)
            )
        if active in ("true", "false"):
            queryset = queryset.filter(active=active == "true")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search_query": self.request.GET.get("q", "").strip(),
                "selected_active": self.request.GET.get("active", "").strip(),
                "can_add": self.request.user.has_perm(
                    "assistencia_social.add_assistedfamily"
                ),
            }
        )
        return context


class AssistedFamilyCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = AssistedFamily
    form_class = AssistedFamilyForm
    template_name = "assistencia_social/family_form.html"
    permission_required = (
        "assistencia_social.add_assistedfamily",
        "assistencia_social.view_assistedfamily",
    )

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Família cadastrada para acompanhamento social.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assisted-family-detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Nova família atendida"
        return context


class AssistedFamilyUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = AssistedFamily
    form_class = AssistedFamilyForm
    template_name = "assistencia_social/family_form.html"
    permission_required = (
        "assistencia_social.change_assistedfamily",
        "assistencia_social.view_assistedfamily",
    )

    def form_valid(self, form):
        messages.success(self.request, "Cadastro da família atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assisted-family-detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Editar família atendida"
        return context


class AssistedFamilyDetailView(
    LoginRequiredMixin, PermissionRequiredMixin, DetailView
):
    model = AssistedFamily
    template_name = "assistencia_social/family_detail.html"
    context_object_name = "family"
    permission_required = "assistencia_social.view_assistedfamily"

    def get_queryset(self):
        return AssistedFamily.objects.prefetch_related("assistance_records")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_change"] = self.request.user.has_perm(
            "assistencia_social.change_assistedfamily"
        )
        context["can_view_assistance"] = self.request.user.has_perm(
            "assistencia_social.view_assistancerecord"
        )
        context["can_add_assistance"] = self.request.user.has_perms(
            (
                "assistencia_social.add_assistancerecord",
                "assistencia_social.view_assistancerecord",
            )
        )
        if context["can_view_assistance"]:
            context["assistance_records"] = self.object.assistance_records.all()
        context["map_query"] = self.object.formatted_address
        return context


class AssistanceRecordCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = AssistanceRecord
    form_class = AssistanceRecordForm
    template_name = "assistencia_social/assistance_form.html"
    permission_required = (
        "assistencia_social.add_assistancerecord",
        "assistencia_social.view_assistedfamily",
        "assistencia_social.view_assistancerecord",
    )

    def get_family(self):
        if not hasattr(self, "_family"):
            self._family = get_object_or_404(
                AssistedFamily, pk=self.kwargs["family_pk"]
            )
        return self._family

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["family"] = self.get_family()
        return kwargs

    def form_valid(self, form):
        form.instance.family = self.get_family()
        form.instance.recorded_by = self.request.user
        if form.instance.status == AssistanceRecord.Status.DELIVERED:
            form.instance.delivered_by = self.request.user
        messages.success(self.request, "Registro de ajuda salvo.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "assisted-family-detail", kwargs={"pk": self.get_family().pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["family"] = self.get_family()
        return context


class AssistanceRecordUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = AssistanceRecord
    form_class = AssistanceRecordForm
    template_name = "assistencia_social/assistance_form.html"
    permission_required = (
        "assistencia_social.change_assistancerecord",
        "assistencia_social.view_assistedfamily",
        "assistencia_social.view_assistancerecord",
    )

    def get_queryset(self):
        return AssistanceRecord.objects.select_related("family")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["family"] = self.get_object().family
        return kwargs

    def form_valid(self, form):
        previous_status = self.get_object().status
        if (
            form.instance.status == AssistanceRecord.Status.DELIVERED
            and previous_status != AssistanceRecord.Status.DELIVERED
        ):
            form.instance.delivered_by = self.request.user
        elif form.instance.status != AssistanceRecord.Status.DELIVERED:
            form.instance.delivered_by = None
        messages.success(self.request, "Registro de ajuda atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "assisted-family-detail", kwargs={"pk": self.object.family_id}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["family"] = self.object.family
        context["form_title"] = "Atualizar registro de ajuda"
        return context


class AssistanceRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AssistanceRecord
    template_name = "assistencia_social/assistance_list.html"
    context_object_name = "assistance_records"
    permission_required = (
        "assistencia_social.view_assistancerecord",
        "assistencia_social.view_assistedfamily",
    )
    paginate_by = 25

    def get_queryset(self):
        queryset, self.filter_form = get_filtered_assistance_records(
            self.request.GET
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = getattr(
            self,
            "filter_form",
            AssistanceRecordFilterForm(self.request.GET),
        )
        summary = self.object_list.aggregate(
            total_count=Count("pk"),
            planned_count=Count(
                "pk", filter=Q(status=AssistanceRecord.Status.PLANNED)
            ),
            delivered_count=Count(
                "pk", filter=Q(status=AssistanceRecord.Status.DELIVERED)
            ),
            cancelled_count=Count(
                "pk", filter=Q(status=AssistanceRecord.Status.CANCELLED)
            ),
            delivered_financial_total=Coalesce(
                Sum(
                    "amount",
                    filter=Q(
                        status=AssistanceRecord.Status.DELIVERED,
                        aid_type=AssistanceRecord.AidType.FINANCIAL,
                    ),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        aid_type_rows = self.object_list.values("aid_type").annotate(
            record_count=Count("pk"),
            delivered_count=Count(
                "pk", filter=Q(status=AssistanceRecord.Status.DELIVERED)
            ),
            delivered_quantity=Sum(
                "quantity", filter=Q(status=AssistanceRecord.Status.DELIVERED)
            ),
            delivered_amount=Coalesce(
                Sum(
                    "amount", filter=Q(status=AssistanceRecord.Status.DELIVERED)
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ).order_by("aid_type")
        aid_type_labels = dict(AssistanceRecord.AidType.choices)
        for row in aid_type_rows:
            row["aid_type_label"] = aid_type_labels[row["aid_type"]]
        context.update(
            {
                "filter_form": filter_form,
                "report_summary": summary,
                "aid_type_rows": aid_type_rows,
            }
        )
        return context


class AssistanceRecordExportView(
    LoginRequiredMixin, PermissionRequiredMixin, View
):
    permission_required = (
        "assistencia_social.view_assistancerecord",
        "assistencia_social.view_assistedfamily",
    )

    def get(self, request, *args, **kwargs):
        queryset, filter_form = get_filtered_assistance_records(request.GET)
        if not filter_form.is_valid():
            return HttpResponse(
                "Filtros inválidos. Corrija as datas e tente exportar novamente.",
                status=400,
                content_type="text/plain; charset=utf-8",
            )
        pdf_content = build_assistance_report_pdf(queryset, filter_form)
        return HttpResponse(
            pdf_content,
            content_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="relatorio-assistencia-social.pdf"'
                )
            },
        )
