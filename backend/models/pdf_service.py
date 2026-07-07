import io
import html
import logging
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.schemas.analysis import AnalyzeResponse

logger = logging.getLogger(__name__)

def generate_verification_pdf(report: AnalyzeResponse) -> bytes:
    """
    Generates a professional PDF verification certificate from an AnalyzeResponse report.

    Args:
        report (AnalyzeResponse): The verified news report model.

    Returns:
        bytes: The raw PDF file content.
    """
    buffer = io.BytesIO()
    
    # 0.5 inch margins = 36 points
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Base styling tokens
    primary_dark = colors.HexColor('#0F172A')
    slate_sub = colors.HexColor('#64748B')
    slate_border = colors.HexColor('#E2E8F0')
    
    # Paragraph styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_dark,
        alignment=1, # Centered
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=slate_sub,
        alignment=1,
        spaceAfter=20
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    
    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )
    
    # Parse verdict labels and determine color theme
    label = (report.final_assessment.label or report.classification.verdict or "UNCERTAIN").upper().replace("_", " ")
    if "REAL" in label:
        verdict_color = colors.HexColor('#10B981') # Emerald
        verdict_bg = colors.HexColor('#ECFDF5')
    elif "FAKE" in label:
        verdict_color = colors.HexColor('#F43F5E') # Rose
        verdict_bg = colors.HexColor('#FFF1F2')
    else:
        verdict_color = colors.HexColor('#F59E0B') # Amber
        verdict_bg = colors.HexColor('#FEF3C7')
    # Use the actual label from the analysis (matches the frontend display)
    verdict_text = f"VERDICT: {label}"
        
    verdict_badge_style = ParagraphStyle(
        'VerdictBadge',
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=verdict_color,
        alignment=1
    )
    
    story = []
    
    # Header Logo / Seal Top
    story.append(Paragraph("<b>CRYPTO NEWS INTEGRITY SYSTEM</b>", ParagraphStyle('SubHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#10B981'), alignment=1, spaceAfter=4)))
    story.append(Paragraph("VERIFICATION AUTHENTICITY CERTIFICATE", title_style))
    story.append(Paragraph("Secured via Cryptographic Smart Contract Anchor & Decentralized Storage on IPFS", subtitle_style))
    
    # 1. Main Verdict Card Banner
    verdict_para = Paragraph(verdict_text, verdict_badge_style)
    
    # Format metadata parameters
    risk_pct = f"{(report.final_assessment.score * 100):.0f}%"
    conf_pct = f"{(report.classification.confidence * 100):.0f}%"
    lang_label = html.escape((report.language or "en").upper())
    plat_label = html.escape((report.platform or "unknown").upper())
    
    score_text = f"<b>Risk Index:</b> {risk_pct}  |  <b>Model Confidence:</b> {conf_pct}  |  <b>Language:</b> {lang_label}  |  <b>Source Platform:</b> {plat_label}"
    score_para = Paragraph(score_text, ParagraphStyle('ScoreText', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#475569'), alignment=1))
    
    verdict_table = Table([[verdict_para], [Spacer(1, 4)], [score_para]], colWidths=[540])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), verdict_bg),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1.5, verdict_color),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 12))
    
    # 2. News Text Block Section
    story.append(Paragraph("VERIFIED STATEMENT SNIPPET", section_heading))
    escaped_news = html.escape(report.text)
    news_text_para = Paragraph(f"<i>\"{escaped_news}\"</i>", ParagraphStyle('NewsTextStyle', parent=body_style, fontSize=10, leading=14, textColor=colors.HexColor('#1E293B')))
    news_table = Table([[news_text_para]], colWidths=[540])
    news_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, slate_border),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(news_table)
    story.append(Spacer(1, 10))
    
    # 3. Explainer Summary / Decision reasoning
    story.append(Paragraph("Linguistic Diagnostics & Analysis reasoning", section_heading))
    raw_reasoning = report.final_assessment.reasoning or report.classification.explanation or "No reasoning details generated."
    escaped_reasoning = html.escape(raw_reasoning)
    reasoning_para = Paragraph(escaped_reasoning, body_style)
    reasoning_table = Table([[reasoning_para]], colWidths=[540])
    reasoning_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 0.5, slate_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(reasoning_table)
    story.append(Spacer(1, 8))
    
    # 4. Source Verification matching table
    story.append(Paragraph("Authoritative Matches / Domain Grounding check", section_heading))
    source_items = report.verification.sources or []
    if not source_items:
        story.append(Paragraph("No matches found against configured authoritative directories.", ParagraphStyle('NoSources', parent=body_style, fontName='Helvetica-Oblique', textColor=slate_sub)))
    else:
        source_table_data = [
            [
                Paragraph("<b>Checked Domain / Authority</b>", body_style),
                Paragraph("<b>Grounding Verdict</b>", body_style),
                Paragraph("<b>Verified Evidence Link</b>", body_style)
            ]
        ]
        for s in source_items:
            confirmed_label = "GROUNDED" if s.confirmed else "NO MENTION"
            confirmed_color = "#10B981" if s.confirmed else "#F43F5E"
            confirmed_para = Paragraph(f"<font color='{confirmed_color}'><b>{confirmed_label}</b></font>", body_style)
            
            escaped_name = html.escape(s.name)
            url_text = html.escape(s.url) if s.url else "N/A"
            url_para = Paragraph(url_text, ParagraphStyle('UrlPara', parent=body_style, fontSize=8, leading=10, textColor=colors.HexColor('#0284C7') if s.url else slate_sub))
            
            source_table_data.append([
                Paragraph(escaped_name, body_style),
                confirmed_para,
                url_para
            ])
            
        source_table = Table(source_table_data, colWidths=[160, 100, 280])
        source_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, slate_border),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(source_table)
    story.append(Spacer(1, 12))
    
    # 5. Blockchain Receipt section
    story.append(Paragraph("Decentralized Blockchain & Storage receipt", section_heading))
    
    esc_network = html.escape(report.blockchain.network or "N/A")
    esc_block = html.escape(str(report.blockchain.block_number or 0))
    esc_tx = html.escape(report.blockchain.transaction_hash or "N/A")
    esc_ipfs = html.escape(report.blockchain.ipfs_hash or "N/A")
    esc_time = html.escape(report.blockchain.timestamp or "N/A")
    
    # Create dark slate blocks for seal variables
    seal_data = [
        [Paragraph("<font color='#94A3B8'><b>Blockchain Network</b></font>", body_style), Paragraph(f"<font color='#F1F5F9'>{esc_network}</font>", body_style)],
        [Paragraph("<font color='#94A3B8'><b>Block Height</b></font>", body_style), Paragraph(f"<font color='#F1F5F9'>{esc_block}</font>", body_style)],
        [Paragraph("<font color='#94A3B8'><b>EVM Transaction Hash</b></font>", body_style), Paragraph(f"<font color='#38BDF8'>{esc_tx}</font>", code_style)],
        [Paragraph("<font color='#94A3B8'><b>Decentralized Storage CID</b></font>", body_style), Paragraph(f"<font color='#38BDF8'>{esc_ipfs}</font>", code_style)],
        [Paragraph("<font color='#94A3B8'><b>Anchor Registered At</b></font>", body_style), Paragraph(f"<font color='#F1F5F9'>{esc_time}</font>", body_style)]
    ]
    
    seal_table = Table(seal_data, colWidths=[140, 400])
    seal_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1E293B')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor('#1E293B')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(seal_table)
    story.append(Spacer(1, 20))
    
    # 6. Certification Disclaimer / Footer
    story.append(Paragraph("<font color='#94A3B8'>This document serves as an immutable verification certificate of the news statement, generated dynamically from the analysis of cryptographic signatures. The on-chain block hash and transaction details verify the integrity receipt and timestamp. Check the storage CID on any public IPFS gateway to download the original JSON metadata verification proof.</font>", ParagraphStyle('FooterStyle', parent=body_style, fontSize=7, leading=9, textColor=slate_sub, alignment=1)))
    
    try:
        doc.build(story)
    except Exception as exc:
        logger.exception("Failed to build PDF template via ReportLab.")
        raise RuntimeError("PDF compilation failed.") from exc
        
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
