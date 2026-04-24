"""Rich PDF report generator with Chinese support, images, and styling.

Uses reportlab with a bundled CJK font fallback chain to produce
a professional, print-ready composition analysis report.
"""

from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font resolution
# ---------------------------------------------------------------------------

def _find_cjk_font() -> str:
    """Return path to a CJK-capable TTF/OTF font, or empty string."""
    # Common Windows CJK font paths
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
        for f in (
            "msyh.ttc",       # Microsoft YaHei
            "msyhbd.ttc",     # Microsoft YaHei Bold
            "simhei.ttf",     # SimHei
            "simsun.ttc",     # SimSun
            "simfang.ttf",    # FangSong
            "STKAITI.TTF",    # KaiTi
        )
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


_CJK_FONT_PATH = _find_cjk_font()
_CJK_FONT_NAME = "CJKFont"


def _register_cjk_font() -> None:
    """Register CJK font with reportlab if available."""
    if not _CJK_FONT_PATH:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        if _CJK_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_CJK_FONT_NAME, _CJK_FONT_PATH))
    except Exception as e:
        logger.warning("Failed to register CJK font: %s", e)


# ---------------------------------------------------------------------------
# Markdown-like text rendering
# ---------------------------------------------------------------------------

def _strip_markdown_images(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Extract ![alt](url) from text, return cleaned text + image list."""
    images: List[Dict[str, str]] = []
    def _repl(m):
        url = m.group(2).strip()
        alt = m.group(1).strip()
        images.append({"url": url, "alt": alt})
        return ""  # Remove image references from text
    clean = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _repl, text)
    return clean, images


def _split_into_paragraphs(text: str) -> List[str]:
    """Split markdown text into paragraphs, respecting headers."""
    lines = text.replace("\r\n", "\n").split("\n")
    paras: List[str] = []
    buf: List[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            buf.append(line)
            continue
        if stripped == "":
            if buf:
                paras.append("\n".join(buf).strip())
                buf = []
            continue
        # Headers start a new paragraph
        if re.match(r"^#{1,4}\s", stripped) or re.match(r"^\d{1,2}[.、．]\s", stripped):
            if buf:
                paras.append("\n".join(buf).strip())
                buf = []
            paras.append(stripped)
            continue
        buf.append(line)

    if buf:
        paras.append("\n".join(buf).strip())
    return [p for p in paras if p]


def _render_markdown_to_flowables(
    text: str,
    style_normal: Any,
    style_h1: Any,
    style_h2: Any,
    style_h3: Any,
    style_quote: Any,
    image_fetcher: Any = None,
) -> Tuple[List[Any], List[Dict[str, str]]]:
    """Convert markdown text to reportlab flowables + extracted images."""
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    # Extract images first
    clean_text, images = _strip_markdown_images(text)
    paragraphs = _split_into_paragraphs(clean_text)

    flowables: List[Any] = []
    for para in paragraphs:
        # Headers
        hm = re.match(r"^(#{1,4})\s+(.*)$", para)
        if hm:
            level = len(hm.group(1))
            content = _escape_xml(hm.group(2).strip())
            style = {1: style_h1, 2: style_h2, 3: style_h3}.get(level, style_h3)
            flowables.append(Paragraph(content, style))
            flowables.append(Spacer(1, 4 * mm))
            continue

        # Numbered heading like "1. 开合之势"
        nm = re.match(r"^(\d{1,2})[.、．]\s+(.*)$", para)
        if nm:
            content = _escape_xml(para)
            flowables.append(Paragraph(content, style_h3))
            flowables.append(Spacer(1, 3 * mm))
            continue

        # Blockquote
        if para.startswith(">"):
            content = _escape_xml(re.sub(r"^>\s?", "", para).strip())
            flowables.append(Paragraph(content, style_quote))
            flowables.append(Spacer(1, 2 * mm))
            continue

        # Table
        if "|" in para and _looks_like_table(para):
            table_flow = _parse_table(para, style_normal)
            if table_flow:
                flowables.append(table_flow)
                flowables.append(Spacer(1, 4 * mm))
            continue

        # Normal paragraph
        content = _inline_format(_escape_xml(para))
        flowables.append(Paragraph(content, style_normal))
        flowables.append(Spacer(1, 3 * mm))

    return flowables, images


def _looks_like_table(line: str) -> bool:
    """Quick check if a line looks like a markdown table."""
    cells = [c.strip() for c in line.split("|") if c.strip()]
    return len(cells) >= 2


def _parse_table(text: str, style_normal: Any) -> Optional[Any]:
    """Parse a simple markdown table into a reportlab Table."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    lines = text.strip().split("\n")
    if len(lines) < 2:
        return None

    header = [c.strip() for c in lines[0].split("|") if c.strip()]
    rows = []
    for line in lines[2:]:  # Skip separator
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if cells:
            rows.append(cells)

    if not rows:
        return None

    data = [header] + rows
    t = Table(data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.18, 0.25, 0.34, 1)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT_NAME if _CJK_FONT_PATH else "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.9, 0.9, 0.87, 1)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.Color(0.97, 0.98, 0.99, 1), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _escape_xml(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _inline_format(text: str) -> str:
    """Apply bold/italic formatting to escaped text."""
    # Bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Also support <bold>text</bold> tags from backend postprocessing
    text = re.sub(r"&lt;bold&gt;([^&]+)&lt;/bold&gt;", r"<b>\1</b>", text)
    # Italic: *text*
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


# ---------------------------------------------------------------------------
# Main PDF generator
# ---------------------------------------------------------------------------

def generate_rich_pdf(
    *,
    task_id: str,
    report: Dict[str, Any],
    original_image_path: Optional[str] = None,
    processed_image_path: Optional[str] = None,
) -> bytes:
    """Generate a full, styled PDF report with Chinese text and images.

    Args:
        task_id: Task identifier.
        report: The full report dict (from report_builder.build_report).
        original_image_path: Path to the original uploaded image.
        processed_image_path: Path to the annotated/processed image.

    Returns:
        PDF bytes.
    """
    _register_cjk_font()

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
        Table, TableStyle, HRFlowable, KeepTogether, PageBreak,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    font = _CJK_FONT_NAME if _CJK_FONT_PATH else "Helvetica"

    # Styles
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font,
        fontSize=22,
        leading=28,
        textColor=colors.Color(0.18, 0.25, 0.34, 1),
        spaceAfter=6 * mm,
    )
    style_subtitle = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        leading=16,
        textColor=colors.Color(0.4, 0.4, 0.4, 1),
        spaceAfter=8 * mm,
    )
    style_h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName=font,
        fontSize=16,
        leading=22,
        textColor=colors.Color(0.18, 0.25, 0.34, 1),
        spaceBefore=10 * mm,
        spaceAfter=4 * mm,
        borderPadding=(0, 0, 2, 0),
    )
    style_h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=13,
        leading=18,
        textColor=colors.Color(1.0, 0.42, 0.21, 1),  # #FF6B35
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        leftIndent=0,
    )
    style_h3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName=font,
        fontSize=11.5,
        leading=17,
        textColor=colors.Color(0.18, 0.25, 0.34, 1),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    style_normal = ParagraphStyle(
        "BodyText2",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10,
        leading=18,
        textColor=colors.Color(0.15, 0.19, 0.22, 1),
        spaceAfter=3 * mm,
        alignment=TA_JUSTIFY,
    )
    style_quote = ParagraphStyle(
        "BlockQuote",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9.5,
        leading=15,
        textColor=colors.Color(0.3, 0.3, 0.3, 1),
        leftIndent=12,
        rightIndent=12,
        borderPadding=6,
        backColor=colors.Color(0.97, 0.98, 0.99, 1),
        spaceAfter=3 * mm,
    )
    style_score = ParagraphStyle(
        "ScoreDisplay",
        parent=styles["Normal"],
        fontName=font,
        fontSize=36,
        leading=42,
        textColor=colors.Color(1.0, 0.42, 0.21, 1),
        alignment=TA_CENTER,
    )
    style_score_label = ParagraphStyle(
        "ScoreLabel",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        leading=16,
        textColor=colors.Color(0.4, 0.4, 0.4, 1),
        alignment=TA_CENTER,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    story: List[Any] = []

    # -- Title page --
    story.append(Paragraph("构图分析报告", style_title))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(0.91, 0.89, 0.86, 1)))
    story.append(Spacer(1, 4 * mm))

    summary = report.get("summary", {})
    total_score = summary.get("total_score", 0)
    grade = summary.get("grade", "")
    story.append(Paragraph(
        f'<font color="#ff6b35" size="36"><b>{total_score}</b></font>'
        f'<font color="#888" size="16"> / 100</font>'
        f'    <font color="#ff6b35" size="20"><b>{grade}</b></font>',
        ParagraphStyle("ScoreHero", parent=styles["Normal"], fontName=font, alignment=TA_CENTER, spaceAfter=6 * mm),
    ))

    # Dimensions table
    dims = report.get("dimensions", [])
    if dims:
        dim_data = [["维度", "得分", "满分", "占比"]]
        for d in dims:
            dim_data.append([
                str(d.get("name", "")),
                str(d.get("score", 0)),
                str(d.get("max", 0)),
                f"{d.get('weight', 0)}%",
            ])
        dim_table = Table(dim_data, colWidths=[55 * mm, 25 * mm, 25 * mm, 25 * mm])
        dim_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.18, 0.25, 0.34, 1)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.9, 0.9, 0.87, 1)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.Color(0.97, 0.98, 0.99, 1), colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(dim_table)
        story.append(Spacer(1, 6 * mm))

    # Original image
    if original_image_path and os.path.isfile(original_image_path):
        try:
            img = _load_image_for_pdf(original_image_path, max_width=140 * mm)
            story.append(img)
            story.append(Spacer(1, 4 * mm))
        except Exception as e:
            logger.warning("Failed to add original image to PDF: %s", e)

    # Arrow overlay image (起承转合)
    arrow_url = report.get("assets", {}).get("arrow_overlay_url", "")
    if arrow_url:
        try:
            from app.core.config import get_settings as _get_settings
            _settings = _get_settings()
            base_data = os.path.dirname(_settings.UPLOAD_DIR)
            arrow_path = os.path.join(base_data, arrow_url.lstrip("/static/"))
            if os.path.isfile(arrow_path):
                arrow_img = _load_image_for_pdf(arrow_path, max_width=140 * mm)
                # Add a section header for arrow analysis
                story.append(Paragraph("起承转合分析", style_h2))
                story.append(arrow_img)
                story.append(Spacer(1, 4 * mm))
                # Add path type and analysis text
                arrow_data = report.get("arrow_analysis") or {}
                path_type = arrow_data.get("path_type", "")
                llm_analysis = arrow_data.get("llm_analysis", "")
                if path_type:
                    story.append(Paragraph(
                        f"<b>路径类型：</b>{_escape_xml(path_type)}",
                        style_normal,
                    ))
                if llm_analysis:
                    story.append(Paragraph(_escape_xml(llm_analysis), style_normal))
        except Exception as e:
            logger.warning("Failed to add arrow overlay to PDF: %s", e)

    story.append(PageBreak())

    # -- LLM Analysis text --
    llm = report.get("llm", {})
    llm_text = llm.get("text", "")
    if llm_text:
        # Image fetcher: resolve relative paths to local files
        base_dir = ""
        if original_image_path:
            base_dir = os.path.dirname(original_image_path)

        def _img_fetcher(url: str) -> Optional[RLImage]:
            try:
                path = url
                if url.startswith("/static/"):
                    # Resolve from backend/data/ directory
                    from app.core.config import get_settings
                    settings = get_settings()
                    base_data = os.path.dirname(settings.UPLOAD_DIR)
                    path = os.path.join(base_data, url.lstrip("/"))
                elif not os.path.isabs(url) and base_dir:
                    path = os.path.join(base_dir, url)
                if os.path.isfile(path):
                    return _load_image_for_pdf(path, max_width=150 * mm)
                return None
            except Exception:
                return None

        flowables, extracted_images = _render_markdown_to_flowables(
            llm_text, style_normal, style_h1, style_h2, style_h3, style_quote,
            image_fetcher=_img_fetcher,
        )
        story.extend(flowables)

        # Append extracted images
        for img_info in extracted_images:
            img_url = img_info.get("url", "")
            rl_img = _img_fetcher(img_url)
            if rl_img:
                story.append(rl_img)
                if img_info.get("alt"):
                    caption_style = ParagraphStyle(
                        "ImgCaption", parent=styles["Normal"], fontName=font,
                        fontSize=8, leading=12, textColor=colors.Color(0.5, 0.5, 0.5, 1),
                        alignment=TA_CENTER, spaceAfter=4 * mm,
                    )
                    story.append(Paragraph(_escape_xml(img_info["alt"]), caption_style))

    # -- Footer note --
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.Color(0.9, 0.9, 0.87, 1)))
    story.append(Paragraph(
        f"报告生成时间：{summary.get('generated_at', '')}  |  规则版本：{report.get('ruleset_version', '')}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontName=font,
                       fontSize=8, textColor=colors.Color(0.6, 0.6, 0.6, 1), alignment=TA_CENTER),
    ))

    doc.build(story)
    return buf.getvalue()


def _load_image_for_pdf(path: str, max_width: float = 150) -> RLImage:
    """Load an image and resize for PDF, maintaining aspect ratio."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage

    img = PILImage.open(path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    w, h = img.size
    aspect = h / max(w, 1)

    # Convert max_width from mm to points (1mm ≈ 2.835pt)
    max_w_pt = max_width
    if w > max_w_pt:
        new_w = max_w_pt
        new_h = new_w * aspect
    else:
        new_w = w
        new_h = h

    img_buf = io.BytesIO()
    img.save(img_buf, format="JPEG", quality=85)
    img_buf.seek(0)
    rl_img = RLImage(img_buf, width=new_w, height=new_h)
    return rl_img


def generate_simple_pdf(*, title: str = "Report", lines: list[str] | None = None) -> bytes:
    """Generate a minimal PDF without reportlab, using basic PDF structure.

    This is a fallback when reportlab is not available.
    """
    import io
    import time

    if lines is None:
        lines = []

    buf = io.BytesIO()

    # Minimal PDF structure
    objects = []

    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Object 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    # Object 3: Page
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")

    # Object 4: Content stream
    text_lines = [f"BT /F1 12 Tf 72 720 Td ({title}) Tj"]
    y = 690
    for line in lines:
        text_lines.append(f"BT /F1 10 Tf 72 {y} Td ({line}) Tj")
        y -= 15

    stream_content = "\n".join(text_lines).encode("latin-1", errors="replace")
    stream = f"4 0 obj\n<< /Length {len(stream_content)} >>\nstream\n".encode() + stream_content + b"\nendstream\nendobj\n"
    objects.append(stream)

    # Object 5: Font
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    # Write PDF
    buf.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(buf.tell())
        buf.write(obj)

    # Cross-reference table
    xref_offset = buf.tell()
    buf.write(b"xref\n")
    buf.write(b"0 6\n")
    buf.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buf.write(f"{offset:010d} 00000 n \n".encode())

    buf.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    buf.write(f"{xref_offset}\n".encode())
    buf.write(b"%%EOF\n")

    return buf.getvalue()
