from pydantic import BaseModel


class UpdateReplyRequest(BaseModel):
    reply: str
