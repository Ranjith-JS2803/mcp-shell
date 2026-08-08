"""Builds a real, multi-section sales report PDF — KPIs, a bar chart of
revenue by region, and a category-breakdown table — not a plain-text
stand-in. Saved to disk (REPORTS_DIR) so a report generated once can be
paged through, and re-read, without regenerating it.
"""

import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from periods import parse_period
from seed.db import get_connection

REPORTS_DIR = Path(os.environ.get("DB_PATH", "./data/mcp_server.db")).resolve().parent / "reports"

ACCENT = colors.HexColor("#5B8DEF")


def _kpis(date_range: tuple[str, str] | None) -> dict:
    conn = get_connection()
    try:
        sql = (
            "SELECT COUNT(*) AS order_count, SUM(total_amount) AS revenue, "
            "AVG(total_amount) AS avg_order_value FROM orders WHERE status != 'cancelled'"
        )
        params: list = []
        if date_range:
            sql += " AND order_date >= ? AND order_date < ?"
            params.extend(date_range)
        row = conn.execute(sql, params).fetchone()
    finally:
        conn.close()
    return {
        "revenue": row["revenue"] or 0,
        "order_count": row["order_count"] or 0,
        "avg_order_value": row["avg_order_value"] or 0,
    }


def _revenue_by_region(date_range: tuple[str, str] | None) -> tuple[list[str], list[float]]:
    conn = get_connection()
    try:
        sql = "SELECT region, SUM(total_amount) AS revenue FROM orders WHERE status != 'cancelled'"
        params: list = []
        if date_range:
            sql += " AND order_date >= ? AND order_date < ?"
            params.extend(date_range)
        sql += " GROUP BY region ORDER BY revenue DESC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [r["region"] for r in rows], [round(r["revenue"], 2) for r in rows]


def _category_breakdown(date_range: tuple[str, str] | None) -> list[tuple[str, float]]:
    conn = get_connection()
    try:
        sql = (
            "SELECT p.category AS category, SUM(oi.quantity * oi.unit_price) AS revenue "
            "FROM order_items oi "
            "JOIN orders o ON o.order_id = oi.order_id "
            "JOIN products p ON p.product_id = oi.product_id "
            "WHERE o.status != 'cancelled'"
        )
        params: list = []
        if date_range:
            sql += " AND o.order_date >= ? AND o.order_date < ?"
            params.extend(date_range)
        sql += " GROUP BY p.category ORDER BY revenue DESC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [(r["category"], round(r["revenue"], 2)) for r in rows]


def _bar_chart(categories: list[str], values: list[float]) -> Drawing:
    drawing = Drawing(440, 200)
    chart = VerticalBarChart()
    chart.x, chart.y = 50, 20
    chart.width, chart.height = 370, 150
    chart.data = [values]
    chart.categoryAxis.categoryNames = categories
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labelTextFormat = "$%.0f"
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = ACCENT
    chart.barWidth = 10
    drawing.add(chart)
    return drawing


def build_report_pdf(report_id: str, period: str | None) -> bytes:
    date_range = parse_period(period)
    kpis = _kpis(date_range)
    categories, values = _revenue_by_region(date_range)
    category_rows = _category_breakdown(date_range)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch, leftMargin=0.7 * inch, rightMargin=0.7 * inch
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    label = f" — {period}" if period else ""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story = [
        Paragraph(f"Sales Report{label}", title_style),
        Paragraph(f"Report ID: {report_id}  ·  Generated {generated_at}", body_style),
        Spacer(1, 0.3 * inch),
        Paragraph("Key Metrics", heading_style),
        Spacer(1, 0.1 * inch),
        Table(
            [
                ["Total Revenue", "Order Count", "Avg Order Value"],
                [
                    f"${kpis['revenue']:,.2f}",
                    f"{kpis['order_count']:,}",
                    f"${kpis['avg_order_value']:,.2f}",
                ],
            ],
            colWidths=[1.8 * inch] * 3,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ]
            ),
        ),
        Spacer(1, 0.35 * inch),
        Paragraph("Revenue by Region", heading_style),
        Spacer(1, 0.1 * inch),
        _bar_chart(categories, values) if categories else Paragraph("No data for this period.", body_style),
        Spacer(1, 0.35 * inch),
        Paragraph("Revenue by Category", heading_style),
        Spacer(1, 0.1 * inch),
        Table(
            [["Category", "Revenue"]] + [[cat, f"${rev:,.2f}"] for cat, rev in category_rows],
            colWidths=[3 * inch, 2 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#232427")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f1f3")]),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ]
            ),
        ),
        Spacer(1, 0.3 * inch),
        Paragraph("Generated by mcp-shell — a reference implementation of MCP artifact rendering.", body_style),
    ]

    doc.build(story)
    return buffer.getvalue()


def save_report(report_id: str, pdf_bytes: bytes) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{report_id}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def read_report(report_id: str) -> bytes:
    path = REPORTS_DIR / f"{report_id}.pdf"
    return path.read_bytes()
