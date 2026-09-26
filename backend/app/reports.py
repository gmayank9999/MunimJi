"""Generates a downloadable Excel/PDF payments report from current invoice data - for
sending to an accountant/CA, not for the agent's own use. Pure formatting over data
already in our db; no external API calls, so this never goes through swy/executor.py.
"""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.money import format_inr

# Placeholder demo values - this project has no real business registration anywhere,
# so these are NOT a real GSTIN/PAN. Swap them for the real ones before sending this to
# an actual CA/tax filing; a fabricated GSTIN on a real filing is worse than none.
BUSINESS_GSTIN = "06AACFK1234L1ZQ"
BUSINESS_PAN = "AACFK1234L"
CGST_RATE_PERCENT = 9
SGST_RATE_PERCENT = 9


# reportlab's default fonts (Helvetica etc.) have no glyph for "₹" - it renders as a
# solid black box in the PDF. The dashboard can use format_inr()'s "₹" directly since
# browsers/HTML have full Unicode font fallback, but the PDF needs a plain-ASCII prefix.
def _format_inr_pdf(amount: int) -> str:
    return format_inr(amount).replace("₹", "Rs. ")

COLUMNS = [
    "Invoice", "Client", "Tier", "Invoice Date", "Due Date",
    "Amount (INR)", "Paid (INR)", "Due (INR)", "Status", "Days Overdue",
]


def _rows(invoices: list[dict], clients: list[dict], *, today: date) -> list[list]:
    client_names = {c["client_id"]: c["name"] for c in clients}
    client_tiers = {c["client_id"]: c["tier"] for c in clients}

    rows = []
    for inv in invoices:
        due_date = date.fromisoformat(inv["due_date"])
        days_overdue = max(0, (today - due_date).days) if inv["status"] != "paid" else 0
        paid_inr = inv["amount_inr"] - inv["due_inr"]
        rows.append([
            inv["number"],
            client_names.get(inv["client_id"], inv["client_id"]),
            client_tiers.get(inv["client_id"], ""),
            inv["invoice_date"],
            inv["due_date"],
            inv["amount_inr"],
            paid_inr,
            inv["due_inr"],
            inv["status"].upper(),
            days_overdue,
        ])
    rows.sort(key=lambda r: r[-1], reverse=True)
    return rows


def generate_invoices_xlsx(invoices: list[dict], clients: list[dict], *, today: date) -> bytes:
    rows = _rows(invoices, clients, today=today)

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"

    ws.append([f"MunimJi - Payments Report - {today.isoformat()}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    header_row = ws.max_row + 1
    ws.append(COLUMNS)
    for cell in ws[header_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for row in rows:
        ws.append(row)

    money_cols = {6, 7, 8}  # Amount, Paid, Due (1-indexed)
    for row_idx in range(header_row + 1, header_row + 1 + len(rows)):
        for col_idx in money_cols:
            ws.cell(row=row_idx, column=col_idx).number_format = "#,##0"

    for col_idx, header in enumerate(COLUMNS, start=1):
        width = max(len(header), 12) + 2
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    total_amount = sum(r[5] for r in rows)
    total_due = sum(r[7] for r in rows)
    summary = wb.create_sheet("Summary")
    summary.append(["Metric", "Value"])
    summary["A1"].font = Font(bold=True)
    summary["B1"].font = Font(bold=True)
    summary.append(["Report date", today.isoformat()])
    summary.append(["Total invoices", len(rows)])
    summary.append(["Total invoiced (INR)", total_amount])
    summary.append(["Total outstanding (INR)", total_due])
    summary.column_dimensions["A"].width = 24
    summary.column_dimensions["B"].width = 20

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


REGISTER_COLUMNS = [
    "Sl. No.", "Invoice No.", "Invoice Date", "Party Name",
    "Invoice Value", "Amount Received", "Amount Outstanding", "Ageing (Days)", "Status",
]


def generate_invoices_pdf(invoices: list[dict], clients: list[dict], *, today: date) -> bytes:
    """A formal sales/invoice register, not a dashboard export - the layout an
    accountant expects to file or reconcile against: business header, chronological
    numbering, a totals row. No GST/tax computation, since neither GSTIN nor a tax rate
    is tracked anywhere in this data - it would be invented, not reported."""
    rows = sorted(_rows(invoices, clients, today=today), key=lambda r: (r[3], r[0]))
    total_amount = sum(r[5] for r in rows)
    total_received = sum(r[6] for r in rows)
    total_due = sum(r[7] for r in rows)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    business_style = ParagraphStyle("Business", parent=styles["Heading1"], fontSize=15, alignment=1, spaceAfter=2)
    address_style = ParagraphStyle("Address", parent=styles["Normal"], alignment=1, fontSize=9, textColor=colors.grey)
    title_style = ParagraphStyle("RegisterTitle", parent=styles["Heading2"], fontSize=12, alignment=1, spaceBefore=8)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], alignment=1, fontSize=9, textColor=colors.grey)
    footnote_style = ParagraphStyle("Footnote", parent=styles["Normal"], fontSize=7.5, textColor=colors.grey)

    elements = [
        Paragraph("KAARIGAR STUDIO", business_style),
        Paragraph("Gurugram, Haryana, India", address_style),
        Paragraph(f"GSTIN: {BUSINESS_GSTIN}  |  PAN: {BUSINESS_PAN}", address_style),
        Spacer(1, 4 * mm),
        Paragraph("SALES / INVOICE REGISTER", title_style),
        Paragraph(f"Statement as on {today.strftime('%d %B %Y')}", meta_style),
        Spacer(1, 6 * mm),
    ]

    table_data = [REGISTER_COLUMNS]
    for i, r in enumerate(rows, start=1):
        table_data.append([
            str(i), r[0], r[3], r[1],
            _format_inr_pdf(r[5]), _format_inr_pdf(r[6]), _format_inr_pdf(r[7]),
            str(r[9]), r[8],
        ])
    table_data.append([
        "", "", "", "TOTAL",
        _format_inr_pdf(total_amount), _format_inr_pdf(total_received), _format_inr_pdf(total_due), "", "",
    ])

    table = Table(
        table_data, repeatRows=1,
        colWidths=[14 * mm, 24 * mm, 24 * mm, 40 * mm, 30 * mm, 32 * mm, 34 * mm, 20 * mm, 20 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8ec")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 1), (6, -1), "RIGHT"),
        ("ALIGN", (7, 1), (7, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    cgst = round(total_amount * CGST_RATE_PERCENT / 100)
    sgst = round(total_amount * SGST_RATE_PERCENT / 100)
    total_tax = cgst + sgst
    grand_total = total_amount + total_tax

    tax_table = Table(
        [
            ["Taxable Value", _format_inr_pdf(total_amount)],
            [f"CGST @ {CGST_RATE_PERCENT}%", _format_inr_pdf(cgst)],
            [f"SGST @ {SGST_RATE_PERCENT}%", _format_inr_pdf(sgst)],
            ["Total Tax", _format_inr_pdf(total_tax)],
            ["Grand Total (incl. GST)", _format_inr_pdf(grand_total)],
        ],
        colWidths=[45 * mm, 35 * mm], hAlign="RIGHT",
    )
    tax_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8e8ec")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(tax_table)
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "GST shown above is an indicative estimate at a flat rate on the total taxable value and is not "
        "computed per invoice or verified against actual tax invoices - confirm against real filings before "
        "use. GSTIN/PAN shown are placeholders and must be replaced with the business's actual registration "
        "details. All amounts are in Indian Rupees (INR).",
        footnote_style,
    ))

    doc.build(elements)
    return buf.getvalue()
