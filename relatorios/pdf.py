import csv
from xml.sax.saxutils import escape

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from financeiro.pdf import BODY, CELL, H2, LIGHT, RED, SLATE, TITLE, _build

HEAD = ParagraphStyle("head", parent=CELL, fontName="ChurchSans-Bold", textColor=colors.white)
RIGHT = ParagraphStyle("right", parent=CELL, alignment=2)
RIGHT_HEAD = ParagraphStyle("righthead", parent=HEAD, alignment=2)
NOTES_BEFORE = (
    ("introduction", "Introdução"),
    ("development", "Desenvolvimento"),
)
NOTES_AFTER = (
    ("conclusion", "Conclusão e considerações"),
    ("recommendations", "Recomendações finais"),
)
NOTE_KEYS = tuple(k for k, _ in NOTES_BEFORE + NOTES_AFTER)


def _note_blocks(notes, items):
    return [(label, notes.get(key, "").strip()) for key, label in items if notes.get(key, "").strip()]


def _note_story(blocks):
    return [KeepTogether([Paragraph(label, H2), Paragraph(_text(text), BODY)]) for label, text in blocks]


def _text(value):
    return escape(str(value)).replace("\n", "<br/>")


def _section_table(section, width):
    right = set(section.right)
    head = [Paragraph(_text(h), RIGHT_HEAD if i in right else HEAD) for i, h in enumerate(section.header)]
    body = [
        [Paragraph(_text(v), RIGHT if i in right else CELL) for i, v in enumerate(row)]
        for row in section.rows
    ]
    table = Table([head] + body, colWidths=[width / len(section.header)] * len(section.header), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), RED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8cfcf")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_pdf(report, data, notes, author):
    width = A4[0] - 36 * mm
    story = [Paragraph(_text(report.title), TITLE)]
    if data.subtitle:
        story.append(Paragraph(_text(data.subtitle), BODY))
    story += _note_story(_note_blocks(notes, NOTES_BEFORE))
    if data.summary:
        story.append(Spacer(1, 6))
        cells = [[Paragraph(f"<b>{_text(label)}</b><br/>{_text(value)}", CELL) for label, value in data.summary]]
        per_row = 4
        chunks = [cells[0][i:i + per_row] for i in range(0, len(cells[0]), per_row)]
        for chunk in chunks:
            chunk += [""] * (per_row - len(chunk))
            box = Table([chunk], colWidths=[width / per_row] * per_row)
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2d6d6")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(box)
    for section in data.sections:
        story.append(Paragraph(_text(section.title), H2))
        if section.rows:
            story.append(_section_table(section, width))
        else:
            story.append(Paragraph("Nenhum registro neste relatório.", BODY))
    story += _note_story(_note_blocks(notes, NOTES_AFTER))
    story += [Spacer(1, 10), Paragraph(f"Elaborado por: {_text(author)}", CELL)]
    return _build(story)


def pdf_download(content, key):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="relatorio-{key}.pdf"'
    return response


def csv_download(report, data, notes, key):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="relatorio-{key}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow([report.title])
    if data.subtitle:
        writer.writerow([data.subtitle])
    for label, text in _note_blocks(notes, NOTES_BEFORE):
        writer.writerow([])
        writer.writerow([label])
        writer.writerow([text])
    for label, value in data.summary:
        writer.writerow([label, value])
    for section in data.sections:
        writer.writerow([])
        writer.writerow([section.title])
        writer.writerow(section.header)
        writer.writerows(section.rows)
    for label, text in _note_blocks(notes, NOTES_AFTER):
        writer.writerow([])
        writer.writerow([label])
        writer.writerow([text])
    return response
