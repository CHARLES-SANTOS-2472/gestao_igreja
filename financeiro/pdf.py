"""PDFs e planilhas do financeiro, com cabeçalho institucional da igreja."""
import csv
import io
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONTS = Path(reportlab_file).resolve().parent / "fonts"
if "ChurchSans" not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont("ChurchSans", str(FONTS / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("ChurchSans-Bold", str(FONTS / "VeraBd.ttf")))

RED = colors.HexColor("#b3202a")
SLATE = colors.HexColor("#2f3e4e")
LIGHT = colors.HexColor("#f4eeee")
LOGO = Path(settings.BASE_DIR) / "static" / "img" / "logo.jpg"

BODY = ParagraphStyle("body", fontName="ChurchSans", fontSize=9.5, leading=13, textColor=SLATE)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11)
H2 = ParagraphStyle("h2", parent=BODY, fontName="ChurchSans-Bold", fontSize=11.5, textColor=RED,
                    spaceBefore=10, spaceAfter=4)
TITLE = ParagraphStyle("title", parent=BODY, fontName="ChurchSans-Bold", fontSize=16, leading=20,
                       textColor=SLATE, spaceAfter=2)


def money(value):
    value = Decimal(value or 0)
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def cnpj_label():
    digits = "".join(ch for ch in settings.CHURCH_CNPJ if ch.isdigit())
    if len(digits) != 14:
        return settings.CHURCH_CNPJ
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _page(canvas, document):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(RED)
    canvas.rect(0, height - 4 * mm, width, 4 * mm, stroke=0, fill=1)
    left = 18 * mm
    if LOGO.exists():
        canvas.drawImage(str(LOGO), left, height - 29 * mm, 18 * mm, 18 * mm,
                         preserveAspectRatio=True, mask="auto")
    canvas.setFillColor(SLATE)
    canvas.setFont("ChurchSans-Bold", 13)
    canvas.drawString(left + 22 * mm, height - 17 * mm, settings.CHURCH_NAME)
    canvas.setFont("ChurchSans", 8.5)
    canvas.drawString(left + 22 * mm, height - 22 * mm, f"CNPJ {cnpj_label()}")
    canvas.drawString(left + 22 * mm, height - 26.5 * mm, settings.CHURCH_ADDRESS)
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(0.8)
    canvas.line(left, height - 32 * mm, width - left, height - 32 * mm)
    canvas.setFont("ChurchSans", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(left, 10 * mm, f"Emitido em {timezone.localtime():%d/%m/%Y %H:%M}")
    canvas.drawRightString(width - left, 10 * mm, f"Página {document.page}")
    canvas.restoreState()


def _table(rows, widths, header=True, align_right=()):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "ChurchSans"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), SLATE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8cfcf")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "ChurchSans-Bold"),
        ]
    for column in align_right:
        style.append(("ALIGN", (column, 0), (column, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def _build(story):
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=38 * mm, bottomMargin=18 * mm, title=settings.CHURCH_NAME,
        author=settings.CHURCH_NAME,
    )
    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()


def pdf_response(content, filename):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def build_report_pdf(context):
    width = A4[0] - 36 * mm
    story = [
        Paragraph("Prestação de contas", TITLE),
        Paragraph(
            f"Período: {context['date_from']:%d/%m/%Y} a {context['date_to']:%d/%m/%Y}. "
            "Somente lançamentos liquidados entram nos totais.", BODY),
        Spacer(1, 6),
        _table(
            [["Receitas recebidas", "Despesas pagas", "Saldo do período"],
             [money(context["income_total"]), money(context["expense_total"]),
              money(context["net_total"])]],
            [width / 3] * 3,
        ),
    ]

    def section(title, header, rows, widths, right):
        story.append(Paragraph(title, H2))
        if rows:
            story.append(_table([header] + rows, widths, align_right=right))
        else:
            story.append(Paragraph("Nenhum lançamento neste período.", BODY))

    section(
        "Por categoria", ["Tipo", "Categoria", "Lançamentos", "Total"],
        [["Receita" if r["kind"] == "income" else "Despesa", r["category__name"], r["count"],
          money(r["total"])] for r in context["category_rows"]],
        [width * .2, width * .4, width * .2, width * .2], (2, 3),
    )
    section(
        "Por forma de recebimento/pagamento", ["Forma", "Lançamentos", "Total"],
        [[r["method_label"], r["count"], money(r["total"])] for r in context["payment_method_rows"]],
        [width * .5, width * .25, width * .25], (1, 2),
    )
    section(
        "Por ministério", ["Ministério", "Receitas", "Despesas", "Saldo"],
        [[r["department__name"] or "Sem ministério", money(r["income"]), money(r["expense"]),
          money(r["net"])] for r in context["department_rows"]],
        [width * .37, width * .21, width * .21, width * .21], (1, 2, 3),
    )
    section(
        "Por evento", ["Evento", "Receitas", "Despesas"],
        [[r["event__title"] or "Sem evento", money(r["income"]), money(r["expense"])]
         for r in context["event_rows"]],
        [width * .5, width * .25, width * .25], (1, 2),
    )
    pending = [[Paragraph(e.title, CELL), e.get_kind_display(), f"{e.due_on:%d/%m/%Y}",
                money(e.amount)] for e in context["pending_transactions"]]
    section(
        "Pendências no período (fora dos totais)", ["Descrição", "Tipo", "Vencimento", "Valor"],
        pending, [width * .46, width * .16, width * .18, width * .2], (3,),
    )
    story += [Spacer(1, 26), _table([["_" * 38, "_" * 38], ["Tesoureiro(a)", "Pastor(a) presidente"]],
                                    [width / 2] * 2, header=False)]
    return _build(story)


def build_receipt_pdf(donation):
    width = A4[0] - 36 * mm
    donor = "Doação anônima" if donation.anonymous or not donation.donor_name else donation.donor_name
    if donation.donation_type == donation.DonationType.MONEY:
        what = f"{money(donation.amount)} em dinheiro"
    else:
        quantity = f"{donation.quantity:g} {donation.unit}".strip() if donation.quantity else ""
        what = f"{donation.description} {('(' + quantity + ')') if quantity else ''}".strip()
    story = [
        Paragraph(f"Recibo de doação nº {donation.pk:05d}", TITLE),
        Spacer(1, 8),
        Paragraph(
            f"Recebemos de <b>{donor}</b>, em {donation.received_on:%d/%m/%Y}, "
            f"a doação de <b>{what}</b>.", BODY),
        Spacer(1, 6),
        Paragraph(f"Destinação: {donation.get_destination_display()}"
                  + (f" — {donation.destination_description}" if donation.destination_description else ""),
                  BODY),
        Spacer(1, 6),
        Paragraph("Agradecemos a sua generosidade. Que Deus abençoe grandemente a sua vida e a "
                  "sua família.", BODY),
        Spacer(1, 40),
        _table([["_" * 40], [settings.CHURCH_SIGNATURE]], [width], header=False),
    ]
    return _build(story)


def report_csv_response(context):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="prestacao-de-contas.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")

    def num(value):
        return f"{Decimal(value or 0):.2f}".replace(".", ",")

    writer.writerow(["Período", f"{context['date_from']:%d/%m/%Y}", f"{context['date_to']:%d/%m/%Y}"])
    writer.writerow(["Receitas recebidas", num(context["income_total"])])
    writer.writerow(["Despesas pagas", num(context["expense_total"])])
    writer.writerow(["Saldo", num(context["net_total"])])
    writer.writerow([])
    writer.writerow(["Tipo", "Categoria", "Lançamentos", "Total"])
    for r in context["category_rows"]:
        writer.writerow(["Receita" if r["kind"] == "income" else "Despesa", r["category__name"],
                         r["count"], num(r["total"])])
    writer.writerow([])
    writer.writerow(["Ministério", "Receitas", "Despesas", "Saldo"])
    for r in context["department_rows"]:
        writer.writerow([r["department__name"] or "Sem ministério", num(r["income"]),
                         num(r["expense"]), num(r["net"])])
    writer.writerow([])
    writer.writerow(["Evento", "Receitas", "Despesas"])
    for r in context["event_rows"]:
        writer.writerow([r["event__title"] or "Sem evento", num(r["income"]), num(r["expense"])])
    return response
