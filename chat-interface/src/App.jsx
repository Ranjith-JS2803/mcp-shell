import { useCallback, useEffect, useRef, useState } from "react";
import ChatThread from "./components/ChatThread.jsx";
import ChatInput from "./components/ChatInput.jsx";
import EmptyState from "./components/EmptyState.jsx";
import { useChatSession } from "./hooks/useChatSession.js";
import { useWebSocket } from "./hooks/useWebSocket.js";
import { getHistory, postChat } from "./api/gatewayClient.js";

// The backend streams as fast as the LLM generates tokens (often faster
// than a human can read) — this paces how quickly revealed text grows,
// independent of how bursty the actual network delivery is.
const REVEAL_INTERVAL_MS = 20;
const REVEAL_CHARS_PER_TICK = 1;

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

  // message_id -> { queue: string, timer: number|null, finalResponse: object|null }
  const revealState = useRef({});

  useEffect(() => {
    getHistory(chatId)
      .then((history) => setMessages(historyToMessages(history)))
      .catch(() => {
        // fresh chat, or gateway briefly unreachable — either way, start empty
      });
  }, [chatId]);

  useEffect(() => {
    // stop all reveal timers on unmount
    return () => {
      Object.values(revealState.current).forEach((s) => s.timer && clearInterval(s.timer));
    };
  }, []);

  const finalizeMessage = useCallback((response) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.role === "agent" && m.message_id === response.message_id
          ? { ...m, status: "done", text: response.text, artifact: response.artifact }
          : m,
      ),
    );
    setSending(false);
  }, []);

  const tick = useCallback(
    (messageId) => {
      const state = revealState.current[messageId];
      if (!state) return;

      if (state.queue.length > 0) {
        const slice = state.queue.slice(0, REVEAL_CHARS_PER_TICK);
        state.queue = state.queue.slice(REVEAL_CHARS_PER_TICK);
        setMessages((prev) =>
          prev.map((m) =>
            m.role === "agent" && m.message_id === messageId
              ? { ...m, status: "streaming", text: m.text + slice }
              : m,
          ),
        );
        return;
      }

      // queue drained
      clearInterval(state.timer);
      if (state.finalResponse) {
        finalizeMessage(state.finalResponse);
        delete revealState.current[messageId];
      } else {
        state.timer = null; // more chunks may still arrive — restarts then
      }
    },
    [finalizeMessage],
  );

  const ensureRevealTimer = useCallback(
    (messageId) => {
      const state = revealState.current[messageId];
      if (state.timer) return;
      state.timer = setInterval(() => tick(messageId), REVEAL_INTERVAL_MS);
    },
    [tick],
  );

  const handlePush = useCallback(
    (event) => {
      if (event.event === "chunk") {
        const messageId = event.message_id;
        if (!revealState.current[messageId]) {
          revealState.current[messageId] = { queue: "", timer: null, finalResponse: null };
        }
        revealState.current[messageId].queue += event.text;
        ensureRevealTimer(messageId);
        return;
      }

      if (event.event === "final") {
        const response = event.response;
        const messageId = response.message_id;
        const state = revealState.current[messageId];

        if (!state || (state.queue.length === 0 && !state.timer)) {
          // Nothing queued or streaming (covers a pure-fallback reply that
          // arrived as one immediate final with no chunk at all) — apply now.
          finalizeMessage(response);
          delete revealState.current[messageId];
        } else {
          state.finalResponse = response; // let the reveal loop apply it once drained
        }
      }
    },
    [ensureRevealTimer, finalizeMessage],
  );

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
