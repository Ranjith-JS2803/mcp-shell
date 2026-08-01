from fastapi import APIRouter, HTTPException

from components import chat_history
from models.history import CreateMessageRequest, UpdateReplyRequest

router = APIRouter()


@router.post("/history")
async def create_message(req: CreateMessageRequest):
    return await chat_history.create_message(req.chat_id, req.message_id, req.user_query)


@router.patch("/history/{chat_id}/{message_id}")
async def update_reply(chat_id: str, message_id: str, req: UpdateReplyRequest):
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
