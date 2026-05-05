from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable
from xml.sax.saxutils import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from backend.models import Snapshot
from backend.timeutil import format_taiwan_wallclock


def _register_cjk_font() -> str:
    """Register a CJK-capable font if available; fallback to Helvetica."""
    candidates = [
        ("NotoSansTC", "C:/Windows/Fonts/msjh.ttc"),
        ("MicrosoftJhengHei", "C:/Windows/Fonts/msjh.ttc"),
        ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
    ]
    for font_name, font_path in candidates:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            continue
    return "Helvetica"


def _shorten(text: str, limit: int = 120) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _soft_break_text(text: str) -> str:
    """Add soft break opportunities so long tokens can wrap in table cells."""
    return (
        text.replace("/", "/ ")
        .replace("-", "- ")
        .replace("_", "_ ")
        .replace("?", "? ")
        .replace("&", "& ")
    )


def _parse_notification_message(message: str) -> tuple[str, str]:
    """
    Split notification message into event title and diff summary.
    Example:
    "您的訂閱 'xxx' 有更新：...." -> ("您的訂閱 'xxx' 有更新", "....")
    """
    raw = (message or "").strip()
    if "有更新：" in raw:
        left, right = raw.split("有更新：", 1)
        title = (left.strip() + "有更新").strip()
        summary = right.strip()
        return title, summary
    return raw or "通知", ""


def _normalize_snapshot_text(text: str, limit: int = 140) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "-"
    return _shorten(cleaned, limit)


def _get_before_after_text(subscription_id: int) -> tuple[str, str]:
    snapshots = (
        Snapshot.query
        .filter_by(subscription_id=subscription_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(2)
        .all()
    )
    if len(snapshots) < 2:
        return "-", _normalize_snapshot_text(snapshots[0].content_text or "") if snapshots else "-"
    after_text = _normalize_snapshot_text(snapshots[0].content_text or "")
    before_text = _normalize_snapshot_text(snapshots[1].content_text or "")
    return before_text, after_text


def _extract_screenshot_web_path(content_full: str | None) -> str | None:
    raw = (content_full or "").strip()
    if "|screenshot:" not in raw:
        return None
    part = raw.split("|screenshot:", 1)[1].strip()
    return part or None


def _resolve_static_image_path(web_path: str | None) -> str | None:
    if not web_path or not web_path.startswith("/static/"):
        return None
    project_root = Path(__file__).resolve().parents[2]
    abs_path = project_root / "frontend" / "static" / web_path.replace("/static/", "", 1)
    if abs_path.exists():
        return str(abs_path)
    return None


def _get_before_after_images(subscription_id: int) -> tuple[str | None, str | None]:
    snapshots = (
        Snapshot.query
        .filter_by(subscription_id=subscription_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(2)
        .all()
    )
    if not snapshots:
        return None, None
    after_img = _resolve_static_image_path(_extract_screenshot_web_path(snapshots[0].content_full))
    before_img = None
    if len(snapshots) > 1:
        before_img = _resolve_static_image_path(_extract_screenshot_web_path(snapshots[1].content_full))
    return before_img, after_img


def _build_image_cell(image_path: str | None, cell_style: ParagraphStyle):
    if not image_path:
        return Paragraph("-", cell_style)
    try:
        img = Image(image_path)
        max_w = 26 * mm
        max_h = 18 * mm
        scale = min(max_w / float(img.imageWidth), max_h / float(img.imageHeight), 1.0)
        img.drawWidth = float(img.imageWidth) * scale
        img.drawHeight = float(img.imageHeight) * scale
        img.hAlign = "CENTER"
        return img
    except Exception:
        return Paragraph("-", cell_style)


def build_notifications_pdf(
    notifications: Iterable,
    *,
    user_email: str,
    max_rows: int = 20,
) -> bytes:
    """
    Build a PDF report with latest notifications in table format.
    notifications: iterable of Notification ORM objects.
    """
    font_name = _register_cjk_font()
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = font_name
    normal.fontSize = 10
    normal.leading = 14
    title_style = styles["Title"]
    title_style.fontName = font_name
    cell_style = ParagraphStyle(
        "CellStyle",
        parent=normal,
        fontName=font_name,
        fontSize=9,
        leading=12,
        wordWrap="CJK",
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    latest_changed_notifications = [
        n for n in list(notifications)
        if "有更新：" in (n.message or "") or "有更新" in (n.message or "")
    ][:max_rows]

    rows = [
        [
            Paragraph("<b>時間（台灣）</b>", cell_style),
            Paragraph("<b>訂閱ID</b>", cell_style),
            Paragraph("<b>狀態</b>", cell_style),
            Paragraph("<b>事件</b>", cell_style),
            Paragraph("<b>變更前（文字）</b>", cell_style),
            Paragraph("<b>變更後（文字）</b>", cell_style),
            Paragraph("<b>變更前（截圖）</b>", cell_style),
            Paragraph("<b>變更後（截圖）</b>", cell_style),
        ]
    ]
    if not latest_changed_notifications:
        rows.append(
            [
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("目前沒有「有更新」通知。", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
            ]
        )

    for n in latest_changed_notifications:
        created = format_taiwan_wallclock(n.created_at)
        event_title, _ = _parse_notification_message(n.message or "")
        before_text, after_text = _get_before_after_text(n.subscription_id)
        before_img_path, after_img_path = _get_before_after_images(n.subscription_id)
        event_title = _soft_break_text(escape(_shorten(event_title, 90)))
        before_text = _soft_break_text(escape(_shorten(before_text, 150)))
        after_text = _soft_break_text(escape(_shorten(after_text, 150)))
        before_img_cell = _build_image_cell(before_img_path, cell_style)
        after_img_cell = _build_image_cell(after_img_path, cell_style)
        rows.append(
            [
                Paragraph(escape(created), cell_style),
                Paragraph(escape(str(n.subscription_id)), cell_style),
                Paragraph("已讀" if bool(n.is_read) else "未讀", cell_style),
                Paragraph(event_title or "-", cell_style),
                Paragraph(before_text or "-", cell_style),
                Paragraph(after_text or "-", cell_style),
                before_img_cell,
                after_img_cell,
            ]
        )

    table = Table(
        rows,
        colWidths=[22 * mm, 10 * mm, 10 * mm, 28 * mm, 34 * mm, 34 * mm, 30 * mm, 30 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9ca3af")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (6, 1), (7, -1), "MIDDLE"),
            ]
        )
    )

    gen_line = f"產生時間（台灣）：{format_taiwan_wallclock(datetime.now(timezone.utc))}"
    story = [
        Paragraph("最新通知報告", title_style),
        Spacer(1, 4 * mm),
        Paragraph(f"使用者：{user_email}", normal),
        Paragraph(f"筆數上限：{max_rows}", normal),
        Paragraph(gen_line, normal),
        Spacer(1, 5 * mm),
        table,
    ]
    doc.build(story)
    return buffer.getvalue()
