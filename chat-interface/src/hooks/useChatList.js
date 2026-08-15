import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "mcp-shell-chats";

function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** The sidebar's list of chats lives in localStorage — just chat_id,
 * title, and a timestamp. Actual message content is never cached here;
 * it's always re-fetched from gateway's /history/{chat_id} when a chat
 * is opened, so this stays tiny and the backend stays the source of truth.
 */
export function useChatList() {
  const [chats, setChats] = useState(loadChats);
  const [activeChatId, setActiveChatId] = useState(() => loadChats()[0]?.chat_id ?? null);
  // Chats created this runtime — a chat in here legitimately has no
  // history yet, so an empty GET /history for it means "hasn't sent a
  // message," not "the backend lost its data." Only chats absent from
  // this set (i.e. loaded from a previous session's persisted list) are
  // candidates for auto-pruning when their history comes back empty.
  const freshChatIds = useRef(new Set());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
  }, [chats]);

  const createChat = useCallback(() => {
    const chat = { chat_id: crypto.randomUUID(), title: "New chat", createdAt: Date.now() };
    freshChatIds.current.add(chat.chat_id);
    setChats((prev) => [chat, ...prev]);
    setActiveChatId(chat.chat_id);
    return chat.chat_id;
  }, []);

  const renameChat = useCallback((chatId, title) => {
    setChats((prev) => prev.map((c) => (c.chat_id === chatId ? { ...c, title } : c)));
  }, []);

  const removeChat = useCallback((chatId) => {
    setChats((prev) => prev.filter((c) => c.chat_id !== chatId));
    freshChatIds.current.delete(chatId);
  }, []);

  const isFreshChat = useCallback((chatId) => freshChatIds.current.has(chatId), []);

  return { chats, activeChatId, setActiveChatId, createChat, renameChat, removeChat, isFreshChat };
}
