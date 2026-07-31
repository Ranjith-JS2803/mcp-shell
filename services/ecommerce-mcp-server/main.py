import os

from mcp.server.mcpserver import MCPServer

import tools

mcp = MCPServer(
    name="mcp-shell-mcp-server",
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
