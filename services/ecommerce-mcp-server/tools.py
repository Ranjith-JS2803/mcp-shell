"""The 4 MCP tools. Each is fully self-contained — its own resource_link,
its own pagination scheme (where it has one), no shared ref-parsing or
template registry between them. That's deliberate: every use case should
be readable in isolation.
"""

import base64
import uuid
from typing import Annotated
from urllib.parse import urlencode

from mcp.types import CallToolResult, ResourceLink, TextContent
from pydantic import Field

import pdf_report
from periods import parse_period
from seed.db import get_connection

PAGE_SIZE = 50
REPORT_CHUNK_BYTES = 600  # small on purpose — makes pagination visibly reflected in the frontend

PeriodArg = Annotated[
    str | None,
    Field(
        default=None,
        description=(
            "Optional period filter. Must be one of these exact formats: "
            "'2026' (a whole year), '2026-Q3' (a quarter, Q1-Q4), or '2026-07' (a month). "
            "Never a phrase like 'this quarter' or 'last year' — resolve those to a real "
            "year/quarter/month yourself before calling this tool. Omit entirely for all-time."
        ),
    ),
]


# ---------------------------------------------------------------------------
# 1. revenue_chart — HTML chart, no pagination
# ---------------------------------------------------------------------------


def revenue_chart(period: PeriodArg = None) -> CallToolResult:
    date_range = parse_period(period)
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

    categories = [r["region"] for r in rows]
    values = [round(r["revenue"], 2) for r in rows]

    return CallToolResult(
        content=[
            ResourceLink(name="Revenue Chart", uri="chart-template://revenue-chart", mimeType="text/html"),
            TextContent(type="text", text=f"Revenue by region{f' for {period}' if period else ''}."),
        ],
        structured_content={
            "categories": categories,
            "values": values,
            "title": f"Revenue by Region{f' — {period}' if period else ''}",
        },
    )


# ---------------------------------------------------------------------------
# 2. orders_report_table — HTML table with page-by-page pagination
# ---------------------------------------------------------------------------


def _orders_table_page(page: int, status: str | None, region: str | None) -> dict:
    where = []
    params: list = []
    if status:
        where.append("status = ?")
        params.append(status)
    if region:
        where.append("region = ?")
        params.append(region)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    offset = (page - 1) * PAGE_SIZE
    conn = get_connection()
    try:
        total_count = conn.execute(f"SELECT COUNT(*) AS n FROM orders {where_sql}", params).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT order_id, customer_id, order_date, status, total_amount, region
            FROM orders {where_sql}
            ORDER BY order_id
            LIMIT ? OFFSET ?
            """,
            [*params, PAGE_SIZE, offset],
        ).fetchall()
    finally:
        conn.close()

    columns = ["order_id", "customer_id", "order_date", "status", "total_amount", "region"]
    row_values = [[r[c] for c in columns] for r in rows]

    next_ref = None
    if offset + len(rows) < total_count:
        query = {k: v for k, v in {"status": status, "region": region}.items() if v}
        next_ref = f"orders-table-page://{page + 1}"
        if query:
            next_ref += f"?{urlencode(query)}"

    return {
        "columns": columns,
        "rows": row_values,
        "total_count": total_count,
        "page": page,
        "next_ref": next_ref,
    }


def orders_report_table(status: str | None = None, region: str | None = None) -> CallToolResult:
    page_data = _orders_table_page(1, status, region)
    return CallToolResult(
        content=[
            ResourceLink(name="Orders Table", uri="orders-table-template://", mimeType="text/html"),
            TextContent(type="text", text=f"Orders page 1 of {page_data['total_count']} total rows."),
        ],
        structured_content=page_data,
    )


def resolve_orders_table_page(page: str, status: str | None = None, region: str | None = None) -> dict:
    """Backs the orders-table-page://{page}{?status,region} resource."""
    return _orders_table_page(int(page), status, region)


# ---------------------------------------------------------------------------
# 3. generate_sales_report — simulated PDF byte stream, auto-paginated
# ---------------------------------------------------------------------------


def _report_chunk(report_id: str, chunk: int) -> dict:
    """Reads the already-rendered PDF back off disk and slices out one
    small byte range — the file is built once by generate_sales_report,
    not regenerated on every page request."""
    pdf_bytes = pdf_report.read_report(report_id)
    total_chunks = -(-len(pdf_bytes) // REPORT_CHUNK_BYTES)  # ceil div
    start = (chunk - 1) * REPORT_CHUNK_BYTES
    raw_slice = pdf_bytes[start : start + REPORT_CHUNK_BYTES]

    next_ref = None
    if chunk < total_chunks:
        next_ref = f"report-bytes-page://{report_id}/{chunk + 1}"

    return {
        "report_id": report_id,
        "chunk": chunk,
        "total_chunks": total_chunks,
        "total_bytes": len(pdf_bytes),
        "data": base64.b64encode(raw_slice).decode("ascii"),
        "next_ref": next_ref,
    }


def generate_sales_report(period: PeriodArg = None) -> CallToolResult:
    report_id = f"rep_{uuid.uuid4().hex[:10]}"
    pdf_bytes = pdf_report.build_report_pdf(report_id, period)
    pdf_report.save_report(report_id, pdf_bytes)

    first_chunk = _report_chunk(report_id, 1)
    return CallToolResult(
        content=[
            ResourceLink(name="Sales Report", uri="pdf-report-template://", mimeType="text/html"),
            TextContent(type="text", text=f"Generated sales report {report_id}{f' for {period}' if period else ''}."),
        ],
        structured_content=first_chunk,
    )


def resolve_report_bytes_page(report_id: str, chunk: str) -> dict:
    """Backs the report-bytes-page://{report_id}/{chunk} resource."""
    return _report_chunk(report_id, int(chunk))


# ---------------------------------------------------------------------------
# 4. system_status — plain text, no resource_link, no structured content
# ---------------------------------------------------------------------------


def system_status() -> CallToolResult:
    conn = get_connection()
    try:
        order_count = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
    finally:
        conn.close()

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=f"mcp-shell ecommerce-mcp-server is up. {order_count} orders in the dataset.",
            )
        ],
    )
