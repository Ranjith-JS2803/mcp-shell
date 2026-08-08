const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || "http://localhost:8003";

function httpUrl(path) {
  return `${GATEWAY_URL}${path}`;
}

export function wsUrl(socketId) {
  const wsBase = GATEWAY_URL.replace(/^http/, "ws");
  return `${wsBase}/ws/${socketId}`;
}

export async function postChat({ chatId, messageId, socketId, userQuery, isFirstMessage }) {
  const res = await fetch(httpUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      message_id: messageId,
      socket_id: socketId,
      user_query: userQuery,
      is_first_message: !!isFirstMessage,
    }),
  });
  if (!res.ok) throw new Error(`POST /chat failed: ${res.status}`);
  return res.json();
}

export async function getHistory(chatId) {
  const res = await fetch(httpUrl(`/history/${chatId}`));
  if (!res.ok) throw new Error(`GET /history failed: ${res.status}`);
  return res.json();
}

export async function getResource(ref) {
  const res = await fetch(httpUrl(`/resource?ref=${encodeURIComponent(ref)}`));
  if (!res.ok) throw new Error(`GET /resource failed: ${res.status}`);
  return res.json();
}
