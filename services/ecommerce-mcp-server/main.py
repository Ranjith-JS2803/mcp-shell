import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import tools

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

mcp = MCPServer(
    name="ecommerce-mcp-server",
    instructions=(
        "E-commerce data tools backed by a seeded 50k-row SQLite dataset. "
        "Every tool returns a template resource_link plus a small aggregated "
        "structuredContent payload — never raw rows."
    ),
)

mcp.tool(name="revenue_by_region", description="Aggregated revenue per region for a given period.")(
    tools.revenue_by_region
)
mcp.tool(name="monthly_revenue_trend", description="Monthly revenue totals over the last N months.")(
    tools.monthly_revenue_trend
)
mcp.tool(name="top_products", description="Top N products by revenue or quantity.")(tools.top_products)
mcp.tool(name="orders_table", description="Paginated order list with status/region/date filters.")(
    tools.orders_table
)
mcp.tool(name="kpi_summary", description="Total revenue, order count, and average order value.")(
    tools.kpi_summary
)
mcp.tool(name="category_breakdown", description="Revenue split by product category.")(tools.category_breakdown)


@mcp.resource("template://{name}", mime_type="text/html")
def get_template(name: str) -> str:
    """Serves a self-contained artifact template by name (e.g. bar-chart-v1)."""
    path = (TEMPLATES_DIR / f"{name}.html").resolve()
    if path.parent != TEMPLATES_DIR or not path.is_file():
        raise FileNotFoundError(f"No such template: {name}")
    return path.read_text()


@mcp.resource("data://{ref}")
def get_data(ref: str) -> dict:
    """Replays a stateless data_source_ref (e.g. orders_table?region=North&cursor=50)
    and returns the matching page of structuredContent — no session state, works
    the same whether called seconds or days after the original tool call."""
    return tools.resolve_ref(ref)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
