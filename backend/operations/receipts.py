"""Documents commerciaux PDF de NexaStock.

ReportLab est volontairement centralisé ici afin que le web et l'API produisent
exactement les mêmes documents, sans dépendance système supplémentaire.
"""

from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


GREEN = colors.HexColor("#087F63")
DARK = colors.HexColor("#0A281F")
MUTED = colors.HexColor("#667A73")
LINE = colors.HexColor("#DCE8E3")
SOFT = colors.HexColor("#F2FAF7")
AMBER = colors.HexColor("#B56B00")

PAYMENT_METHOD_LABELS = {
    "CASH": "Espèces",
    "MOBILE_MONEY": "Mobile Money",
    "BANK_TRANSFER": "Virement bancaire",
    "CREDIT": "Crédit",
}
PAYMENT_STATUS_LABELS = {
    "PAID": "Payée",
    "PARTIAL": "Partiellement payée",
    "UNPAID": "À payer",
    "PENDING": "À payer",
    "CANCELLED": "Annulée",
}


def _number(value):
    number = Decimal(str(value or 0))
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money(value):
    return f"{Decimal(str(value or 0)):,.0f}".replace(",", " ")


def _styles():
    styles = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "Brand", parent=styles["Heading1"], fontName="Helvetica-Bold",
            fontSize=17, leading=20, textColor=DARK, spaceAfter=2,
        ),
        "document": ParagraphStyle(
            "Document", parent=styles["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=10, textColor=GREEN, uppercase=True,
            tracking=1.2,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=7.5, leading=9,
            textColor=colors.white,
        ),
        "title": ParagraphStyle(
            "Title", parent=styles["Heading2"], fontName="Helvetica-Bold",
            fontSize=15, leading=19, textColor=DARK, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body", parent=styles["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=12, textColor=DARK,
        ),
        "muted": ParagraphStyle(
            "Muted", parent=styles["Normal"], fontName="Helvetica",
            fontSize=7.5, leading=10, textColor=MUTED,
        ),
        "right": ParagraphStyle(
            "Right", parent=styles["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=12, textColor=DARK, alignment=TA_RIGHT,
        ),
        "center": ParagraphStyle(
            "Center", parent=styles["Normal"], fontName="Helvetica",
            fontSize=8, leading=11, textColor=MUTED, alignment=TA_CENTER,
        ),
        "total": ParagraphStyle(
            "Total", parent=styles["Normal"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=DARK, alignment=TA_RIGHT,
        ),
    }


def _company_details(company):
    details = [company.name]
    if getattr(company, "city", ""):
        details.append(company.city)
    if getattr(company, "phone", ""):
        details.append(f"Tél. {company.phone}")
    if getattr(company, "email", ""):
        details.append(company.email)
    return "<br/>".join(details)


def _header(company, document_label, document_number, styles):
    company_block = [
        Paragraph("NexaStock", styles["brand"]),
        Paragraph(_company_details(company), styles["muted"]),
    ]
    document_block = [
        Paragraph(document_label.upper(), styles["document"]),
        Paragraph(str(document_number), styles["title"]),
    ]
    header = Table([[company_block, document_block]], colWidths=[105 * mm, 65 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 1, GREEN),
    ]))
    return header


def _information_table(rows, styles, widths=(35 * mm, 50 * mm, 35 * mm, 50 * mm)):
    cells = []
    for label, value in rows:
        cells.extend([
            Paragraph(str(label).upper(), styles["muted"]),
            Paragraph(str(value or "—"), styles["body"]),
        ])
    if len(cells) % 4:
        cells.extend(["", ""])
    table = Table([cells[index:index + 4] for index in range(0, len(cells), 4)], colWidths=widths)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .25, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _items_table(headers, rows, widths, styles):
    data = [[Paragraph(header, styles["table_header"]) for header in headers]]
    for row in rows:
        data.append([
            Paragraph(str(value), styles["right"] if index else styles["body"])
            for index, value in enumerate(row)
        ])
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 1), (-1, -1), .35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _totals_table(rows, currency, styles):
    data = []
    for label, value, strong in rows:
        label_style = styles["body"] if not strong else styles["title"]
        value_style = styles["right"] if not strong else styles["total"]
        data.append([
            Paragraph(label, label_style),
            Paragraph(f"{_money(value)} {currency}", value_style),
        ])
    table = Table(data, colWidths=[45 * mm, 48 * mm], hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, -1), (-1, -1), 1, GREEN),
    ]))
    return table


def _build(story, *, pagesize=A4, title="NexaStock"):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=pagesize, title=title, author="NexaStock",
        rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(doc.leftMargin, 10 * mm, pagesize[0] - doc.rightMargin, 10 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(doc.leftMargin, 6 * mm, "Document généré par NexaStock")
        canvas.drawRightString(pagesize[0] - doc.rightMargin, 6 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def render_sale_document(sale, items, company, *, invoice=False):
    styles = _styles()
    currency = company.currency
    document_label = "Facture de vente" if invoice else "Reçu de vente"
    rows = [
        [
            f"<b>{item['name']}</b><br/><font color='#667A73'>{item.get('code', '')}</font>",
            f"{_number(item['quantity_packages'])} colis",
            f"{_money(item['unit_price'])} {currency}",
            f"{_money(item.get('discount_amount', 0))} {currency}",
            f"<b>{_money(item['total_amount'])} {currency}</b>",
        ]
        for item in items
    ]
    story = [
        _header(company, document_label, sale["sale_number"], styles),
        Spacer(1, 8 * mm),
        _information_table([
            ("Date", sale["sale_date"].strftime("%d/%m/%Y")),
            ("Client", sale["customer_name"]),
            ("Commercial", sale.get("salesperson_name") or "—"),
            ("Paiement", PAYMENT_METHOD_LABELS.get(sale["payment_method"], sale["payment_method"])),
        ], styles),
        Spacer(1, 7 * mm),
        _items_table(
            ["Produit", "Quantité", "Prix unitaire", "Remise", "Montant"],
            rows,
            [62 * mm, 25 * mm, 30 * mm, 24 * mm, 32 * mm],
            styles,
        ),
        Spacer(1, 6 * mm),
        _totals_table([
            ("Sous-total", sale["subtotal"], False),
            ("Remise", sale["discount_amount"], False),
            ("Total", sale["total_amount"], True),
        ], currency, styles),
        Spacer(1, 8 * mm),
        KeepTogether([
            Paragraph(
                f"Statut : <b>{PAYMENT_STATUS_LABELS.get(sale['payment_status'], sale['payment_status'])}</b>",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "Merci pour votre confiance. Conservez ce document comme justificatif de l'opération.",
                styles["center"],
            ),
        ]),
    ]
    return _build(story, pagesize=A4, title=f"{document_label} {sale['sale_number']}")


def render_purchase_receipt_document(receipt, items, company):
    styles = _styles()
    currency = company.currency
    rows = [
        [
            f"<b>{item['name']}</b><br/><font color='#667A73'>{item['code']}</font>",
            f"{_number(item['quantity_packages'])} colis",
            f"{_money(item['unit_cost'])} {currency}",
            f"<b>{_money(item['total_cost'])} {currency}</b>",
        ]
        for item in items
    ]
    story = [
        _header(company, "Bon de réception", receipt["receipt_number"], styles),
        Spacer(1, 8 * mm),
        _information_table([
            ("Date de réception", receipt["receipt_date"].strftime("%d/%m/%Y")),
            ("Fournisseur", receipt["supplier_name"]),
            ("Statut", receipt.get("status_label") or receipt["status"]),
            ("Référence", receipt["receipt_number"]),
        ], styles),
        Spacer(1, 7 * mm),
        _items_table(
            ["Produit", "Quantité reçue", "Coût unitaire", "Montant"], rows,
            [76 * mm, 32 * mm, 33 * mm, 32 * mm], styles,
        ),
        Spacer(1, 6 * mm),
        _totals_table([("Total réceptionné", receipt["total_amount"], True)], currency, styles),
        Spacer(1, 3 * mm),
        _signature_block(styles),
    ]
    return _build(story, title=f"Bon de réception {receipt['receipt_number']}")


def render_purchase_order_document(order, company):
    styles = _styles()
    currency = company.currency
    total = sum((item.quantity_ordered * item.unit_cost for item in order.items.all()), Decimal("0"))
    rows = [
        [
            f"<b>{item.product_name}</b><br/><font color='#667A73'>{item.product_code}</font>",
            f"{_number(item.quantity_ordered)} colis",
            f"{_money(item.unit_cost)} {currency}",
            f"<b>{_money(item.quantity_ordered * item.unit_cost)} {currency}</b>",
        ]
        for item in order.items.all()
    ]
    story = [
        _header(company, "Bon de commande", order.order_number, styles),
        Spacer(1, 8 * mm),
        _information_table([
            ("Fournisseur", order.supplier_name),
            ("Statut", order.get_status_display()),
            ("Créée le", order.created_at.strftime("%d/%m/%Y")),
            ("Livraison prévue", order.expected_date.strftime("%d/%m/%Y") if order.expected_date else "À convenir"),
        ], styles),
        Spacer(1, 7 * mm),
        _items_table(
            ["Produit", "Quantité", "Coût indicatif", "Montant estimé"], rows,
            [76 * mm, 31 * mm, 34 * mm, 32 * mm], styles,
        ),
        Spacer(1, 6 * mm),
        _totals_table([("Total estimé", total, True)], currency, styles),
    ]
    if order.notes:
        story.extend([
            Spacer(1, 7 * mm),
            Paragraph("NOTE AU FOURNISSEUR", styles["document"]),
            Spacer(1, 2 * mm),
            Paragraph(order.notes, styles["body"]),
        ])
    story.extend([Spacer(1, 3 * mm), _signature_block(styles)])
    return _build(story, title=f"Bon de commande {order.order_number}")


def _signature_block(styles):
    table = Table([
        [
            Paragraph(
                "<b>Pour le dépôt</b><br/>Signature et cachet : ____________________",
                styles["muted"],
            ),
            Paragraph(
                "<b>Pour le fournisseur</b><br/>Signature et cachet : ____________________",
                styles["muted"],
            ),
        ],
    ], colWidths=[85 * mm, 85 * mm], splitByRow=0)
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


# Compatibilité limitée avec les appels historiques, le temps que tous les
# consommateurs soient migrés vers les fonctions structurées ci-dessus.
def sale_receipt_lines(sale, items, company):
    return sale, items, company


def render_receipt_pdf(payload):
    sale, items, company = payload
    return render_sale_document(sale, items, company)
