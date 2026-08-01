"""The 4 MCP tools. Each is fully self-contained — its own resource_link,
its own pagination scheme (where it has one), no shared ref-parsing or
template registry between them. That's deliberate: every use case should
be readable in isolation.
"""

from urllib.parse import urlencode

from mcp.types import CallToolResult, ResourceLink, TextContent

from periods import parse_period
from seed.db import get_connection

PAGE_SIZE = 50
REPORT_CHUNK_SIZE = 3  # lines of the simulated report per chunk


# ---------------------------------------------------------------------------
# 1. revenue_chart — HTML chart, no pagination
# ---------------------------------------------------------------------------


def revenue_chart(period: str | None = None) -> CallToolResult:
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


def _report_lines(report_id: str, period: str | None) -> list[str]:
    date_range = parse_period(period)
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

    label = f" — {period}" if period else ""
    return [
        f"SALES REPORT{label}",
        f"Report ID: {report_id}",
        "=" * 40,
        f"Total Revenue:     ${row['revenue'] or 0:,.2f}",
        f"Order Count:       {row['order_count'] or 0}",
        f"Avg Order Value:   ${row['avg_order_value'] or 0:,.2f}",
        "-" * 40,
        "This is a simulated report body — bytes are",
        "streamed chunk-by-chunk to demonstrate the",
        "same pagination contract as orders_report_table,",
        "just applied to a binary/document artifact",
        "instead of tabular rows.",
        "=" * 40,
        "End of report.",
    ]


def _report_chunk(report_id: str, period: str | None, chunk: int) -> dict:
    lines = _report_lines(report_id, period)
    total_chunks = -(-len(lines) // REPORT_CHUNK_SIZE)  # ceil div
    start = (chunk - 1) * REPORT_CHUNK_SIZE
    chunk_lines = lines[start : start + REPORT_CHUNK_SIZE]

    next_ref = None
    if chunk < total_chunks:
        next_ref = f"report-bytes-page://{report_id}/{chunk + 1}"
        if period:
            next_ref += f"?{urlencode({'period': period})}"

    return {
        "report_id": report_id,
        "chunk": chunk,
        "total_chunks": total_chunks,
        "data": "\n".join(chunk_lines) + "\n",
        "next_ref": next_ref,
    }


def generate_sales_report(period: str | None = None) -> CallToolResult:
    report_id = f"rep_{abs(hash((period, 'sales'))) % 100000:05d}"
    first_chunk = _report_chunk(report_id, period, 1)
    return CallToolResult(
        content=[
            ResourceLink(name="Sales Report", uri="pdf-report-template://", mimeType="text/html"),
            TextContent(type="text", text=f"Generated sales report {report_id}{f' for {period}' if period else ''}."),
        ],
        structured_content=first_chunk,
    )


def resolve_report_bytes_page(report_id: str, chunk: str, period: str | None = None) -> dict:
    """Backs the report-bytes-page://{report_id}/{chunk}{?period} resource."""
    return _report_chunk(report_id, period, int(chunk))


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
