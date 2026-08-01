from pydantic import BaseModel


class CreateMessageRequest(BaseModel):
    chat_id: str
    message_id: str
    user_query: str


class UpdateReplyRequest(BaseModel):
    reply: str
