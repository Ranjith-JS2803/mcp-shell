from pydantic import BaseModel


class ChatRequest(BaseModel):
    chat_id: str
    message_id: str
    socket_id: str
    user_query: str
