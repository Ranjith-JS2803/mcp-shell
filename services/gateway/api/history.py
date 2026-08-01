from fastapi import APIRouter, HTTPException

from components import chat_history
from models.history import UpdateReplyRequest

router = APIRouter()


@router.patch("/history/{chat_id}/{message_id}")
async def update_reply(chat_id: str, message_id: str, req: UpdateReplyRequest):
    """The one API llm-agent calls to write back a message's final
    response — creation happens in gateway itself, before llm-agent is
    ever invoked, so this is the only history write llm-agent needs."""
    await chat_history.update_reply(chat_id, message_id, req.reply)
    return {"status": "ok"}


@router.get("/history/{chat_id}")
async def get_chat_history(chat_id: str):
    return await chat_history.get_chat_history(chat_id)


@router.get("/history/{chat_id}/{message_id}")
async def get_message(chat_id: str, message_id: str):
    doc = await chat_history.get_message(chat_id, message_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No such chat history entry")
    return doc
