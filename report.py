"""One-page PDF assembly, same visual system as the sales guide (teal, no branding)."""
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

INK = HexColor('#1a2332')
ACCENT = HexColor('#0e6e6e')
LIGHT = HexColor('#eef4f4')
WARN = HexColor('#8a2c2c')
WARNBG = HexColor('#f9eeee')
GRAY = HexColor('#5a6572')
RULE = HexColor('#c9d4d4')
GREEN = HexColor('#2f7d4f')
GREENBG = HexColor('#eaf4ee')

VERDICT_COLORS = {
    "GREEN": (GREEN, GREENBG),
    "GOOD FIT": (ACCENT, LIGHT),
    "PAUSE": (WARN, WARNBG),
    "OPEN FIELD": (GRAY, LIGHT),
}

STYLES = {
    'h1': ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=INK),
    'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=9.5, leading=12, textColor=GRAY),
    'chip': ParagraphStyle('chip', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=white, alignment=TA_CENTER),
    'headline': ParagraphStyle('headline', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=ACCENT, spaceBefore=6, spaceAfter=6),
    'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=ACCENT, spaceBefore=10, spaceAfter=4),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.3, leading=12.5, textColor=INK),
    'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.3, leading=10.5, textColor=INK),
    'quote': ParagraphStyle('quote', fontName='Helvetica-Oblique', fontSize=9.3, leading=12.5, textColor=INK, leftIndent=10, spaceAfter=5),
    'finding_ok': ParagraphStyle('finding_ok', fontName='Helvetica', fontSize=9.3, leading=12.5, textColor=INK),
    'footer': ParagraphStyle('footer', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=ACCENT, spaceBefore=8),
}

ENGINES = ["ChatGPT", "Perplexity", "Gemini"]


def _competitor_hint(quote):
    if not quote:
        return ""
    matches = re.findall(r"([A-Z][a-zA-Z&'.]+(?:\s+[A-Z][a-zA-Z&'.]+){1,3})", quote)
    if matches:
        return matches[0]
    words = quote.split()
    return " ".join(words[:6]) + ("..." if len(words) > 6 else "")


def _rating_line(resolve):
    if not resolve["profile_found"]:
        return {"passed": None, "finding": "no Google Business Profile found"}
    rating = resolve["rating"]
    count = resolve["review_count"]
    days = resolve["newest_review_days"]
    if rating is None:
        return {"passed": None, "finding": "no Google Business Profile found"}
    recency = f"newest review {days} days ago" if days is not None else "review recency unknown"
    return {"passed": rating >= 4.0, "finding": f"{rating} stars, {count} reviews, {recency}"}


def generate_report(data, output_path):
    business, city, date_str = data["business"], data["city"], data["date"]
    resolve = data["resolve"]
    verdict = resolve["verdict"]
    color, bg = VERDICT_COLORS.get(verdict, (GRAY, LIGHT))

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
    )
    S = []
    P = Paragraph

    # ---- header ----
    chip = Table([[P(verdict, STYLES['chip'])]], colWidths=[1.4 * inch])
    chip.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    title = P(f"<b>{business}</b>", STYLES['h1'])
    sub = P(f"{city}  |  {date_str}", STYLES['sub'])
    header = Table([[[title, sub], chip]], colWidths=[doc.width - 1.4 * inch, 1.4 * inch])
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    S.append(header)
    S.append(Spacer(1, 10))

    # ---- headline number ----
    cells = data["aiquery"]
    total = len(cells)
    named_count = sum(1 for c in cells if c["mentioned"] is True)
    S.append(P(f"Named in {named_count} of {total} AI answers", STYLES['headline']))

    # ---- the table that sells ----
    labels = list(dict.fromkeys(c["prompt_label"] for c in cells))
    by_key = {(c["prompt_label"], c["engine"]): c for c in cells}
    rows = [[P("<b>Prompt</b>", STYLES['cell'])] + [P(f"<b>{e}</b>", STYLES['cell']) for e in ENGINES]]
    for label in labels:
        row = [P(label, STYLES['cell'])]
        for engine in ENGINES:
            cell = by_key.get((label, engine))
            if cell is None or cell.get("error"):
                row.append(P("N/A", STYLES['cell']))
            elif cell["mentioned"]:
                row.append(P('<font color="#2f7d4f"><b>YES</b></font>', STYLES['cell']))
            else:
                hint = _competitor_hint(cell["quote"])
                row.append(P(f'<font color="#8a2c2c"><b>NO</b></font> - {hint}', STYLES['cell']))
        rows.append(row)

    col0 = 1.3 * inch
    table = Table(rows, colWidths=[col0] + [(doc.width - col0) / 3] * 3)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, RULE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    S.append(table)
    S.append(Spacer(1, 6))

    # ---- verbatim quotes ----
    quotes = [c["quote"] for c in cells if c.get("mentioned") is False and c.get("quote")]
    seen = set()
    picked = []
    for q in quotes:
        if q not in seen:
            seen.add(q)
            picked.append(q)
        if len(picked) == 3:
            break
    if picked:
        S.append(P("What AI says instead", STYLES['h2']))
        for q in picked:
            S.append(P(f'"{q}"', STYLES['quote']))

    # ---- technical findings ----
    S.append(P("Technical findings", STYLES['h2']))
    checks = data["checks"]
    findings = [
        ("Crawler access", checks["crawler"]),
        ("Structured data", checks["schema"]),
        ("Bing indexation", checks["bing"]),
        ("Review profile", _rating_line(resolve)),
    ]
    for name, result in findings:
        if result["passed"] is True:
            tag, tag_color = "PASS", "#2f7d4f"
        elif result["passed"] is False:
            tag, tag_color = "FLAG", "#8a2c2c"
        else:
            tag, tag_color = "N/A", "#5a6572"
        S.append(P(
            f'<font color="{tag_color}"><b>{tag}</b></font> &nbsp; <b>{name}:</b> {result["finding"]}',
            STYLES['body'],
        ))

    # ---- footer sales line ----
    S.append(P("Every flagged item above is fixable. Ask us how.", STYLES['footer']))

    doc.build(S)
    return output_path
