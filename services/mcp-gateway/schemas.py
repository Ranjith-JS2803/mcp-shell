from pydantic import BaseModel


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = {}
    chat_id: str
    msg_id: str


class ToolCallMeta(BaseModel):
    truncated: bool
    cache_hit: bool
    payload_bytes: int


class ToolCallResponse(BaseModel):
    snapshot_id: str
    template_ref: str | None
    template_html: str | None
    data: dict | None
    summary: str | None
    meta: ToolCallMeta
