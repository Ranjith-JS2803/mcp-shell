import { useRef } from "react";

function getOrCreate(key) {
  let value = sessionStorage.getItem(key);
  if (!value) {
    value = crypto.randomUUID();
    sessionStorage.setItem(key, value);
  }
  return value;
}

/** One chat per browser session — persisted so a page refresh doesn't start a new chat. */
export function useChatSession() {
  const chatId = useRef(getOrCreate("mcp-shell-chat-id")).current;
  const socketId = useRef(getOrCreate("mcp-shell-socket-id")).current;
  return { chatId, socketId };
}
