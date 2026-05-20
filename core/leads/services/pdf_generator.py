"""
pdf_generator.py
Generates a professional, personalized audit report PDF using ReportLab.
"""
import os, re
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak,
)
from reportlab.platypus.flowables import Flowable
import gc

# ── Palette ────────────────────────────────────────────────────────────────
C = {
    "dark":    colors.HexColor("#0D1117"),
    "accent":  colors.HexColor("#4F8EF7"),
    "acc_lt":  colors.HexColor("#EBF2FF"),
    "mid":     colors.HexColor("#6B7280"),
    "light":   colors.HexColor("#F3F4F6"),
    "body":    colors.HexColor("#374151"),
    "dark_tx": colors.HexColor("#111827"),
    "green":   colors.HexColor("#10B981"),
    "amber":   colors.HexColor("#F59E0B"),
    "white":   colors.white,
}

W, H = A4
MARGIN = 18 * mm
CW = W - 2 * MARGIN   # content width


# ── Custom flowables ───────────────────────────────────────────────────────
class SectionBanner(Flowable):
    def __init__(self, text, width=CW):
        super().__init__()
        self.text  = text
        self.width = width
        self.height = 26

    def draw(self):
        c = self.canv
        c.setFillColor(C["acc_lt"])
        c.roundRect(0, 0, self.width, self.height, 4, stroke=0, fill=1)
        c.setFillColor(C["accent"])
        c.rect(0, 0, 4, self.height, stroke=0, fill=1)
        c.setFillColor(C["dark_tx"])
        c.setFont("Helvetica-Bold", 10)
        c.drawString(12, 8, self.text.upper())


class CoverBlock(Flowable):
    """Full-width dark hero block for the cover page."""
    def __init__(self, company, prepared_for, date_str, width=W, height=120*mm):
        super().__init__()
        self.company     = company
        self.prepared_for = prepared_for
        self.date_str    = date_str
        self.width       = width
        self.height      = height

    def draw(self):
        c = self.canv
        c.setFillColor(C["dark"])
        c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        # Accent stripe
        c.setFillColor(C["accent"])
        c.rect(0, self.height - 6, self.width, 6, stroke=0, fill=1)
        # Brand
        c.setFillColor(C["accent"])
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, self.height - 28, "SimplifIQ")
        c.setFillColor(colors.HexColor("#4B5563"))
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN, self.height - 42, "AI-Powered Business Intelligence")
        # Title
        c.setFillColor(C["white"])
        c.setFont("Helvetica-Bold", 28)
        c.drawString(MARGIN, self.height - 75, "Business Audit Report")
        # Company name
        c.setFillColor(C["accent"])
        c.setFont("Helvetica-Bold", 18)
        c.drawString(MARGIN, self.height - 97, self.company)
        # Meta
        c.setFillColor(colors.HexColor("#9CA3AF"))
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN, 14, f"Prepared for: {self.prepared_for}   ·   {self.date_str}   ·   CONFIDENTIAL")


# ── Styles ─────────────────────────────────────────────────────────────────
def _styles():
    return {
        "body": ParagraphStyle("Body", fontName="Helvetica", fontSize=10,
                               textColor=C["body"], leading=16, alignment=TA_JUSTIFY, spaceAfter=6),
        "label": ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=8,
                                textColor=C["mid"], leading=11, spaceBefore=4),
        "value": ParagraphStyle("Value", fontName="Helvetica", fontSize=10,
                                textColor=C["dark_tx"], leading=14, spaceAfter=4),
        "bullet": ParagraphStyle("Bullet", fontName="Helvetica", fontSize=10,
                                 textColor=C["body"], leading=15, leftIndent=8, spaceAfter=3),
        "callout": ParagraphStyle("Callout", fontName="Helvetica-Oblique", fontSize=11,
                                  textColor=colors.HexColor("#1E3A5F"), leading=17,
                                  leftIndent=14, spaceAfter=6),
        "bold_body": ParagraphStyle("BoldBody", fontName="Helvetica-Bold", fontSize=10,
                                    textColor=C["dark_tx"], leading=15, spaceAfter=3),
        "impact_high": ParagraphStyle("ImpHigh", fontName="Helvetica-Bold", fontSize=8,
                                      textColor=C["white"], leading=10),
        "impact_med": ParagraphStyle("ImpMed", fontName="Helvetica-Bold", fontSize=8,
                                     textColor=C["white"], leading=10),
    }


# ── Page callbacks ─────────────────────────────────────────────────────────
def _page_cb(company):
    def cb(canv, doc):
        if doc.page > 1:
            canv.setFillColor(C["dark"])
            canv.rect(0, H - 12*mm, W, 12*mm, stroke=0, fill=1)
            canv.setFillColor(C["accent"])
            canv.setFont("Helvetica-Bold", 8)
            canv.drawString(MARGIN, H - 8*mm, "SimplifIQ")
            canv.setFillColor(C["white"])
            canv.setFont("Helvetica", 8)
            canv.drawRightString(W - MARGIN, H - 8*mm,
                                 f"Confidential — {company} Audit Report")
        canv.setFillColor(colors.HexColor("#E5E7EB"))
        canv.rect(0, 0, W, 9*mm, stroke=0, fill=1)
        canv.setFillColor(C["mid"])
        canv.setFont("Helvetica", 7)
        canv.drawString(MARGIN, 3*mm,
                        f"Generated by SimplifIQ · {datetime.utcnow().strftime('%B %Y')}")
        canv.drawRightString(W - MARGIN, 3*mm, f"Page {doc.page}")
    return cb


# ── Helper builders ─────────────────────────────────────────────────────────
def _bullet(text, st):
    return Paragraph(f"<bullet>&bull;</bullet> {text}", st["bullet"])


def _kv_table(pairs: list, st) -> Table:
    """Renders a two-column key/value table."""
    data = [[Paragraph(k, st["label"]), Paragraph(v, st["value"])] for k, v in pairs]
    t = Table(data, colWidths=[45*mm, CW - 45*mm])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C["white"], C["light"]]),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [4, 4, 4, 4]),
    ]))
    return t


def _solution_card(sol: dict, st, idx: int) -> Table:
    impact_color = C["green"] if sol.get("impact", "").lower() == "high" else C["amber"]
    badge_text   = sol.get("impact", "").upper()
    badge_para   = Paragraph(badge_text, st["impact_high"])
    title_para   = Paragraph(f"<b>{idx}. {sol['title']}</b>", st["bold_body"])
    desc_para    = Paragraph(sol["description"], st["body"])
    inner = Table(
        [[title_para, badge_para],
         [desc_para, ""]],
        colWidths=[CW - 28*mm, 24*mm],
    )
    inner.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("SPAN",         (0, 1), (-1, 1)),
        ("BACKGROUND",   (1, 0), (1, 0), impact_color),
        ("ROUNDEDCORNERS", (1, 0), (1, 0), [4, 4, 4, 4]),
        ("ALIGN",        (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING",  (1, 0), (1, 0), 4),
        ("RIGHTPADDING", (1, 0), (1, 0), 4),
        ("TOPPADDING",   (1, 0), (1, 0), 4),
        ("BOTTOMPADDING",(1, 0), (1, 0), 4),
    ]))
    wrapper = Table([[inner]], colWidths=[CW])
    wrapper.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C["light"]),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 6, 6]),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
    ]))
    return wrapper


# ── Main entry point ────────────────────────────────────────────────────────
def generate_report(lead: dict, enriched: dict) -> str:
    from django.conf import settings as djs
    reports_dir = Path(djs.REPORTS_DIR)
    reports_dir.mkdir(exist_ok=True,parents=True)

    safe     = re.sub(r"[^\w\-]", "_", lead["company"])
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filepath = str(reports_dir / f"SimplifIQ_Report_{safe}_{ts}.pdf")

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16*mm, bottomMargin=14*mm,
    )

    st    = _styles()
    story = []
    cb    = _page_cb(lead["company"])

    # ── COVER ────────────────────────────────────────────────────────────
    date_str = datetime.utcnow().strftime("%d %B %Y")
    story.append(CoverBlock(
        company=lead["company"],
        prepared_for=f"{lead['name']} ({lead['email']})",
        date_str=date_str,
        width=W + 2 * MARGIN,   # bleed to edges
        height=115*mm,
    ))
    story.append(Spacer(1, 8*mm))

    # Quick meta row
    meta_data = [
        [Paragraph("INDUSTRY", st["label"]),
         Paragraph("CONTACT", st["label"]),
         Paragraph("TEAM SIZE", st["label"]),
         Paragraph("STAGE", st["label"])],
        [Paragraph(lead["industry"], st["value"]),
         Paragraph(lead.get("role") or "—", st["value"]),
         Paragraph(lead.get("team_size") or "—", st["value"]),
         Paragraph(enriched.get("growth_stage", "—"), st["value"])],
    ]
    meta_t = Table(meta_data, colWidths=[CW/4]*4)
    meta_t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C["light"]),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 6*mm))

    # ── SECTION 1: Executive Summary ─────────────────────────────────────
    story.append(SectionBanner("1. Executive Summary"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(enriched.get("personalized_opening", ""), st["callout"]))
    story.append(Paragraph(enriched.get("company_overview", ""), st["body"]))
    story.append(Spacer(1, 4*mm))

    # ── SECTION 2: Company Intelligence ──────────────────────────────────
    story.append(SectionBanner("2. Company Intelligence"))
    story.append(Spacer(1, 4))

    kv_pairs = [
        ("Value Proposition",  enriched.get("value_proposition", "—")),
        ("Target Market",      enriched.get("target_market", "—")),
        ("Business Model",     enriched.get("business_model", "—")),
        ("Technology Signals", enriched.get("technology_signals", "—")),
    ]
    story.append(_kv_table(kv_pairs, st))
    story.append(Spacer(1, 4*mm))

    # Strengths & Challenges two-up
    strengths   = enriched.get("key_strengths", [])
    challenges  = enriched.get("potential_challenges", [])
    sc_data = [[
        Paragraph("<b>Key Strengths</b>", st["bold_body"]),
        Paragraph("<b>Potential Challenges</b>", st["bold_body"]),
    ]]
    max_rows = max(len(strengths), len(challenges))
    for i in range(max_rows):
        s = Paragraph(f"✓  {strengths[i]}", st["bullet"]) if i < len(strengths) else Paragraph("", st["bullet"])
        ch = Paragraph(f"⚠  {challenges[i]}", st["bullet"]) if i < len(challenges) else Paragraph("", st["bullet"])
        sc_data.append([s, ch])
    sc_t = Table(sc_data, colWidths=[CW/2 - 2*mm, CW/2 - 2*mm], hAlign="LEFT")
    sc_t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#F0FDF4")),
        ("BACKGROUND",   (1, 0), (1, -1), colors.HexColor("#FFFBEB")),
        ("BOX",          (0, 0), (0, -1), 0.4, colors.HexColor("#D1FAE5")),
        ("BOX",          (1, 0), (1, -1), 0.4, colors.HexColor("#FDE68A")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sc_t)
    story.append(Spacer(1, 4*mm))

    # ── SECTION 3: Industry Context ───────────────────────────────────────
    story.append(SectionBanner("3. Industry Context & Opportunity"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(enriched.get("industry_context", ""), st["body"]))
    story.append(Spacer(1, 3*mm))
    ai_opps = enriched.get("ai_opportunity_areas", [])
    if ai_opps:
        story.append(Paragraph("<b>AI Opportunity Areas Identified:</b>", st["bold_body"]))
        for opp in ai_opps:
            story.append(_bullet(opp, st))
    story.append(Spacer(1, 4*mm))

    # ── SECTION 4: Recommended Solutions ─────────────────────────────────
    story.append(SectionBanner("4. Recommended Solutions"))
    story.append(Spacer(1, 4))
    solutions = enriched.get("recommended_solutions", [])
    for i, sol in enumerate(solutions, 1):
        story.append(_solution_card(sol, st, i))
        story.append(Spacer(1, 3*mm))

    story.append(Spacer(1, 2*mm))

    # ── SECTION 5: ROI Projection ─────────────────────────────────────────
    story.append(SectionBanner("5. Expected ROI & Impact"))
    story.append(Spacer(1, 4))
    story.append(Paragraph(enriched.get("estimated_roi_narrative", ""), st["body"]))
    story.append(Spacer(1, 3*mm))

    # ROI visual estimate strip
    roi_data = [
        [Paragraph("30–50%", st["bold_body"]),
         Paragraph("2–4 weeks", st["bold_body"]),
         Paragraph("3× ROI", st["bold_body"])],
        [Paragraph("Manual overhead reduction", st["label"]),
         Paragraph("Typical onboarding time", st["label"]),
         Paragraph("Average within 90 days", st["label"])],
    ]
    roi_t = Table(roi_data, colWidths=[CW/3]*3)
    roi_t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C["acc_lt"]),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("BOX",          (0, 0), (-1, -1), 0.5, C["accent"]),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#BFDBFE")),
    ]))
    story.append(roi_t)
    story.append(Spacer(1, 6*mm))

    # Pain points section (if provided)
    if lead.get("pain_points"):
        story.append(SectionBanner("6. Addressing Your Specific Pain Points"))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<b>{lead['name']}</b> indicated the following challenges: "
            f"<i>{lead['pain_points']}</i>", st["body"]))
        story.append(Paragraph(
            "Our team has worked with companies at similar stages facing identical hurdles. "
            "The recommended solutions above are prioritised specifically to address these concerns "
            "and deliver measurable improvements in your day-to-day operations.",
            st["body"]))
        story.append(Spacer(1, 4*mm))

    # ── CTA / Next steps ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionBanner("Next Steps"))
    story.append(Spacer(1, 6))

    steps = [
        ("Schedule a Discovery Call",
         "Book a 30-minute call with our solutions team to walk through this report together."),
        ("Custom Pilot Design",
         "We'll design a 2-week pilot tailored to one high-impact workflow at your company."),
        ("ROI Measurement Framework",
         "We set up shared dashboards so you can see exactly what's improving, week by week."),
        ("Full Deployment",
         "Once results are validated, we scale the automation across your organisation."),
    ]
    for i, (title, desc) in enumerate(steps, 1):
        step_t = Table(
            [[Paragraph(str(i), ParagraphStyle("Num", fontName="Helvetica-Bold", fontSize=14,
                                               textColor=C["white"], alignment=TA_CENTER)),
              Paragraph(f"<b>{title}</b><br/>{desc}", st["body"])]],
            colWidths=[12*mm, CW - 12*mm],
        )
        step_t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (0, 0), C["accent"]),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C["acc_lt"]]),
            ("BOX",          (0, 0), (-1, -1), 0.4, colors.HexColor("#BFDBFE")),
        ]))
        story.append(step_t)
        story.append(Spacer(1, 3*mm))

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width=CW, thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "This report was automatically generated by SimplifIQ's AI research engine. "
        "All insights are based on publicly available information and form-submitted data. "
        "For questions, reach us at hello@simplifiq.ai",
        ParagraphStyle("Disclaimer", fontName="Helvetica-Oblique", fontSize=8,
                       textColor=C["mid"], leading=12, alignment=TA_CENTER)
    ))

    # Build
    doc.build(story, onFirstPage=cb, onLaterPages=cb)
    gc.collect()
    print(f"  ✓ PDF generated: {filepath}")
    return filepath