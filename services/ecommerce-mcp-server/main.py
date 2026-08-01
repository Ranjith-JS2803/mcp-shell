import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import tools

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

mcp = MCPServer(
    name="ecommerce-mcp-server",
    instructions=(
        "E-commerce data tools backed by a seeded 50k-row SQLite dataset. "
        "Each tool owns its own resource(s) independently — no shared "
        "template registry or ref-resolving between them."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

mcp.tool(name="revenue_chart", description="Revenue by region as an HTML bar chart.")(tools.revenue_chart)
mcp.tool(name="orders_report_table", description="Paginated order list rendered as an HTML table.")(
    tools.orders_report_table
)
mcp.tool(name="generate_sales_report", description="Generates a sales report, streamed as simulated PDF bytes.")(
    tools.generate_sales_report
)
mcp.tool(name="system_status", description="Plain-text health check of the server and dataset.")(
    tools.system_status
)

# ---------------------------------------------------------------------------
# 1. revenue_chart's resource — one static template, nothing else
# ---------------------------------------------------------------------------


@mcp.resource("chart-template://revenue-chart", mime_type="text/html")
def get_revenue_chart_template() -> str:
    return (TEMPLATES_DIR / "revenue-chart.html").read_text()


# ---------------------------------------------------------------------------
# 2. orders_report_table's resources — its own template + its own pager
# ---------------------------------------------------------------------------


@mcp.resource("orders-table-template://", mime_type="text/html")
def get_orders_table_template() -> str:
    return (TEMPLATES_DIR / "orders-table.html").read_text()


@mcp.resource("orders-table-page://{page}{?status,region}")
def get_orders_table_page(page: str, status: str | None = None, region: str | None = None) -> dict:
    return tools.resolve_orders_table_page(page, status, region)


# ---------------------------------------------------------------------------
# 3. generate_sales_report's resources — its own viewer + its own pager
# ---------------------------------------------------------------------------


@mcp.resource("pdf-report-template://", mime_type="text/html")
def get_pdf_report_template() -> str:
    return (TEMPLATES_DIR / "pdf-report-viewer.html").read_text()


@mcp.resource("report-bytes-page://{report_id}/{chunk}{?period}")
def get_report_bytes_page(report_id: str, chunk: str, period: str | None = None) -> dict:
    return tools.resolve_report_bytes_page(report_id, chunk, period)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
