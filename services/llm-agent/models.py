from pydantic import BaseModel


class ChatRequest(BaseModel):
    chat_id: str
    message_id: str
    socket_id: str
    user_query: str
    is_first_message: bool = False


class Artifact(BaseModel):
    template_ref: str
    template_html: str | None
    data: dict | None


class ChatResponse(BaseModel):
    chat_id: str
    message_id: str
    type: str  # "artifact" | "text" — this is the envelope shape a future
    # websocket stream would emit per-chunk; for now it's just returned
    # whole in one HTTP response.
    text: str
    artifact: Artifact | None = None
