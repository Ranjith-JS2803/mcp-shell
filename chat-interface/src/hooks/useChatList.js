import { useCallback, useEffect, useState } from "react";

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

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
  }, [chats]);

  const createChat = useCallback(() => {
    const chat = { chat_id: crypto.randomUUID(), title: "New chat", createdAt: Date.now() };
    setChats((prev) => [chat, ...prev]);
    setActiveChatId(chat.chat_id);
    return chat.chat_id;
  }, []);

  const renameChat = useCallback((chatId, title) => {
    setChats((prev) => prev.map((c) => (c.chat_id === chatId ? { ...c, title } : c)));
  }, []);

  return { chats, activeChatId, setActiveChatId, createChat, renameChat };
}
