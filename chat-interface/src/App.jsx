import { useCallback, useEffect, useState } from "react";
import ChatThread from "./components/ChatThread.jsx";
import ChatInput from "./components/ChatInput.jsx";
import EmptyState from "./components/EmptyState.jsx";
import { useChatSession } from "./hooks/useChatSession.js";
import { useWebSocket } from "./hooks/useWebSocket.js";
import { getHistory, postChat } from "./api/gatewayClient.js";

function historyToMessages(history) {
  const messages = [];
  for (const doc of history) {
    messages.push({
      message_id: `${doc.message_id}-user`,
      role: "user",
      status: "done",
      text: doc.user_query,
      artifact: null,
    });
    messages.push({
      message_id: doc.message_id,
      role: "agent",
      status: doc.reply ? "done" : "pending",
      text: doc.reply || "",
      artifact: doc.artifact || null,
    });
  }
  return messages;
}

export default function App() {
  const { chatId, socketId } = useChatSession();
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    getHistory(chatId)
      .then((history) => setMessages(historyToMessages(history)))
      .catch(() => {
        // fresh chat, or gateway briefly unreachable — either way, start empty
      });
  }, [chatId]);

  const handlePush = useCallback((event) => {
    if (event.event === "chunk") {
      setMessages((prev) =>
        prev.map((m) =>
          m.role === "agent" && m.message_id === event.message_id
            ? { ...m, status: "streaming", text: m.text + event.text }
            : m,
        ),
      );
      return;
    }

    if (event.event === "final") {
      const response = event.response;
      setMessages((prev) =>
        prev.map((m) =>
          m.role === "agent" && m.message_id === response.message_id
            ? { ...m, status: "done", text: response.text, artifact: response.artifact }
            : m,
        ),
      );
      setSending(false);
    }
  }, []);

  useWebSocket(socketId, handlePush);

  async function handleSend(userQuery) {
    const messageId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { message_id: `${messageId}-user`, role: "user", status: "done", text: userQuery, artifact: null },
      { message_id: messageId, role: "agent", status: "pending", text: "", artifact: null },
    ]);
    setSending(true);

    try {
      await postChat({ chatId, messageId, socketId, userQuery });
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === messageId
            ? { ...m, status: "done", text: "Could not reach the server. Please try again." }
            : m,
        ),
      );
      setSending(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">mcp-shell</header>
      <main className="app-main">
        {messages.length === 0 ? <EmptyState onPick={handleSend} /> : <ChatThread messages={messages} />}
      </main>
      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
