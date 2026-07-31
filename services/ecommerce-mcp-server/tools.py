"""The 6 MCP tools. Every function returns a CallToolResult carrying a
resource_link (which template to render) + a small aggregated
structuredContent payload — never raw rows.
"""

from mcp.types import CallToolResult, ResourceLink, TextContent

from periods import parse_period
from refs import parse_ref, build_ref
from seed.db import get_connection

TEMPLATES = {
    "bar-chart-v1": ("template://bar-chart-v1", "Bar Chart"),
    "line-chart-v1": ("template://line-chart-v1", "Line Chart"),
    "table-v1": ("template://table-v1", "Table"),
    "kpi-card-v1": ("template://kpi-card-v1", "KPI Card"),
}

MAX_ROWS = 500  # belt-and-suspenders — the gateway also enforces this, but a
# tool should never even hand it something to enforce against.


def _result(template: str, structured_content: dict, summary: str) -> CallToolResult:
    uri, name = TEMPLATES[template]
    return CallToolResult(
        content=[
            ResourceLink(name=name, uri=uri, mimeType="text/html"),
            TextContent(type="text", text=summary),
        ],
        structured_content=structured_content,
    )


def revenue_by_region(period: str | None = None) -> CallToolResult:
    date_range = parse_period(period)
    conn = get_connection()
    try:
        sql = (
            "SELECT region, SUM(total_amount) AS revenue FROM orders "
            "WHERE status != 'cancelled'"
        )
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
    total_rows = len(rows)

    return _result(
        "bar-chart-v1",
        {
            "categories": categories,
            "values": values,
            "total_rows": total_rows,
            "data_source_ref": build_ref("revenue_by_region", period=period),
        },
        f"Revenue by region{f' for {period}' if period else ''} across {total_rows} regions.",
    )


def monthly_revenue_trend(months: int = 12) -> CallToolResult:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS revenue
            FROM orders
            WHERE status != 'cancelled'
            GROUP BY month
            ORDER BY month DESC
            LIMIT ?
            """,
            (months,),
        ).fetchall()
    finally:
        conn.close()

    rows = list(reversed(rows))
    labels = [r["month"] for r in rows]
    values = [round(r["revenue"], 2) for r in rows]

    return _result(
        "line-chart-v1",
        {
            "labels": labels,
            "values": values,
            "total_rows": len(rows),
            "data_source_ref": build_ref("monthly_revenue_trend", months=months),
        },
        f"Monthly revenue trend over the last {len(rows)} months.",
    )


def top_products(n: int = 10, by: str = "revenue") -> CallToolResult:
    n = min(n, MAX_ROWS)
    metric_sql = "SUM(oi.quantity * oi.unit_price)" if by == "revenue" else "SUM(oi.quantity)"
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT p.name AS product_name, {metric_sql} AS metric
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN products p ON p.product_id = oi.product_id
            WHERE o.status != 'cancelled'
            GROUP BY p.product_id
            ORDER BY metric DESC
            LIMIT ?
            """,
            (n,),
        ).fetchall()
    finally:
        conn.close()

    categories = [r["product_name"] for r in rows]
    values = [round(r["metric"], 2) for r in rows]

    return _result(
        "bar-chart-v1",
        {
            "categories": categories,
            "values": values,
            "total_rows": len(rows),
            "data_source_ref": build_ref("top_products", n=n, by=by),
        },
        f"Top {len(rows)} products by {by}.",
    )


def orders_table(
    status: str | None = None,
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: int = 0,
    limit: int = 50,
) -> CallToolResult:
    limit = min(limit, MAX_ROWS)
    where = []
    params: list = []
    if status:
        where.append("status = ?")
        params.append(status)
    if region:
        where.append("region = ?")
        params.append(region)
    if date_from:
        where.append("order_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("order_date < ?")
        params.append(date_to)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection()
    try:
        total_count = conn.execute(
            f"SELECT COUNT(*) AS n FROM orders {where_sql}", params
        ).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT order_id, customer_id, order_date, status, total_amount, region
            FROM orders {where_sql}
            ORDER BY order_id
            LIMIT ? OFFSET ?
            """,
            [*params, limit, cursor],
        ).fetchall()
    finally:
        conn.close()

    columns = ["order_id", "customer_id", "order_date", "status", "total_amount", "region"]
    row_values = [[r[c] for c in columns] for r in rows]
    next_cursor = cursor + limit if cursor + limit < total_count else None

    return _result(
        "table-v1",
        {
            "columns": columns,
            "rows": row_values,
            "total_count": total_count,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "total_rows": len(rows),
            "data_source_ref": build_ref(
                "orders_table",
                status=status,
                region=region,
                date_from=date_from,
                date_to=date_to,
                cursor=cursor,
                limit=limit,
            ),
        },
        f"Orders {cursor + 1}-{cursor + len(rows)} of {total_count}.",
    )


def kpi_summary(period: str | None = None) -> CallToolResult:
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

    kpis = [
        {"label": "Total Revenue", "value": round(row["revenue"] or 0, 2), "unit": "USD"},
        {"label": "Order Count", "value": row["order_count"] or 0},
        {"label": "Avg Order Value", "value": round(row["avg_order_value"] or 0, 2), "unit": "USD"},
    ]

    return _result(
        "kpi-card-v1",
        {
            "kpis": kpis,
            "total_rows": 1,
            "data_source_ref": build_ref("kpi_summary", period=period),
        },
        f"KPI summary{f' for {period}' if period else ''}.",
    )


def category_breakdown(period: str | None = None) -> CallToolResult:
    date_range = parse_period(period)
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

    categories = [r["category"] for r in rows]
    values = [round(r["revenue"], 2) for r in rows]

    return _result(
        "bar-chart-v1",
        {
            "categories": categories,
            "values": values,
            "total_rows": len(rows),
            "data_source_ref": build_ref("category_breakdown", period=period),
        },
        f"Revenue by category{f' for {period}' if period else ''} across {len(rows)} categories.",
    )


# Registry + int-typed param names, so a data_source_ref string (built by
# build_ref) can be parsed back into a real call — this is what the data://
# resource uses to serve pagination/drill-down without going through
# tools/call again.
REGISTRY = {
    "revenue_by_region": revenue_by_region,
    "monthly_revenue_trend": monthly_revenue_trend,
    "top_products": top_products,
    "orders_table": orders_table,
    "kpi_summary": kpi_summary,
    "category_breakdown": category_breakdown,
}

INT_PARAMS = {"months", "n", "cursor", "limit"}


def resolve_ref(ref: str) -> dict:
    """Replays a data_source_ref and returns its structuredContent."""
    tool_name, params = parse_ref(ref)
    if tool_name not in REGISTRY:
        raise ValueError(f"Unknown tool in data_source_ref: {tool_name}")
    typed_params = {k: (int(v) if k in INT_PARAMS else v) for k, v in params.items()}
    result = REGISTRY[tool_name](**typed_params)
    return result.structured_content
