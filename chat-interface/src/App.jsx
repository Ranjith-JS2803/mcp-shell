import { useCallback, useEffect, useRef, useState } from "react";
import ChatThread from "./components/ChatThread.jsx";
import ChatInput from "./components/ChatInput.jsx";
import EmptyState from "./components/EmptyState.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useChatList } from "./hooks/useChatList.js";
import { useSocketId } from "./hooks/useSocketId.js";
import { useWebSocket } from "./hooks/useWebSocket.js";
import { getHistory, postChat } from "./api/gatewayClient.js";

// The backend streams as fast as the LLM generates tokens (often faster
// than a human can read) — this paces how quickly revealed text grows,
// independent of how bursty the actual network delivery is.
const REVEAL_INTERVAL_MS = 20;
const REVEAL_CHARS_PER_TICK = 1;
const TITLE_MAX_LENGTH = 42;

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

function truncateTitle(text) {
  const trimmed = text.trim();
  return trimmed.length > TITLE_MAX_LENGTH ? `${trimmed.slice(0, TITLE_MAX_LENGTH - 1)}…` : trimmed;
}

export default function App() {
  const socketId = useSocketId();
  const { chats, activeChatId, setActiveChatId, createChat, renameChat } = useChatList();
  const [messagesByChat, setMessagesByChat] = useState({});
  const [sendingByChat, setSendingByChat] = useState({});
  const loadedChatsRef = useRef(new Set());
  const didInitRef = useRef(false);

  // message_id -> { chatId, queue: string, timer: number|null, finalResponse: object|null }
  const revealState = useRef({});

  // First run: no chats yet — start one so the app isn't an empty sidebar.
  // Guarded against StrictMode's double-invoke, which would otherwise
  // create two chats on a fresh visit.
  useEffect(() => {
    if (didInitRef.current) return;
    didInitRef.current = true;
    if (chats.length === 0) createChat();
  }, [chats.length, createChat]);

  // Lazily fetch history the first time a chat is opened.
  useEffect(() => {
    if (!activeChatId || loadedChatsRef.current.has(activeChatId)) return;
    loadedChatsRef.current.add(activeChatId);
    getHistory(activeChatId)
      .then((history) => {
        if (history.length) {
          setMessagesByChat((prev) => ({ ...prev, [activeChatId]: historyToMessages(history) }));
        }
      })
      .catch(() => {
        // fresh chat, or gateway briefly unreachable — either way, start empty
      });
  }, [activeChatId]);

  useEffect(() => {
    return () => {
      Object.values(revealState.current).forEach((s) => s.timer && clearInterval(s.timer));
    };
  }, []);

  const updateChatMessages = useCallback((chatId, updater) => {
    setMessagesByChat((prev) => ({ ...prev, [chatId]: updater(prev[chatId] || []) }));
  }, []);

  const finalizeMessage = useCallback(
    (chatId, response) => {
      updateChatMessages(chatId, (msgs) =>
        msgs.map((m) =>
          m.role === "agent" && m.message_id === response.message_id
            ? { ...m, status: "done", text: response.text, artifact: response.artifact }
            : m,
        ),
      );
      setSendingByChat((prev) => ({ ...prev, [chatId]: false }));
    },
    [updateChatMessages],
  );

  const tick = useCallback(
    (messageId) => {
      const state = revealState.current[messageId];
      if (!state) return;

      if (state.queue.length > 0) {
        const slice = state.queue.slice(0, REVEAL_CHARS_PER_TICK);
        state.queue = state.queue.slice(REVEAL_CHARS_PER_TICK);
        updateChatMessages(state.chatId, (msgs) =>
          msgs.map((m) =>
            m.role === "agent" && m.message_id === messageId
              ? { ...m, status: "streaming", text: m.text + slice }
              : m,
          ),
        );
        return;
      }

      clearInterval(state.timer);
      if (state.finalResponse) {
        finalizeMessage(state.chatId, state.finalResponse);
        delete revealState.current[messageId];
      } else {
        state.timer = null; // more chunks may still arrive — restarts then
      }
    },
    [finalizeMessage, updateChatMessages],
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
          revealState.current[messageId] = { chatId: event.chat_id, queue: "", timer: null, finalResponse: null };
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
          finalizeMessage(response.chat_id, response);
          delete revealState.current[messageId];
        } else {
          state.finalResponse = response;
        }
      }
    },
    [ensureRevealTimer, finalizeMessage],
  );

  useWebSocket(socketId, handlePush);

  async function handleSend(userQuery) {
    const chatId = activeChatId;
    const messageId = crypto.randomUUID();
    const isFirstMessage = !(messagesByChat[chatId]?.length);

    updateChatMessages(chatId, (msgs) => [
      ...msgs,
      { message_id: `${messageId}-user`, role: "user", status: "done", text: userQuery, artifact: null },
      { message_id: messageId, role: "agent", status: "pending", text: "", artifact: null },
    ]);
    setSendingByChat((prev) => ({ ...prev, [chatId]: true }));

    if (isFirstMessage) renameChat(chatId, truncateTitle(userQuery));

    try {
      await postChat({ chatId, messageId, socketId, userQuery });
    } catch {
      updateChatMessages(chatId, (msgs) =>
        msgs.map((m) =>
          m.message_id === messageId
            ? { ...m, status: "done", text: "Could not reach the server. Please try again." }
            : m,
        ),
      );
      setSendingByChat((prev) => ({ ...prev, [chatId]: false }));
    }
  }

  const messages = messagesByChat[activeChatId] || [];
  const sending = !!sendingByChat[activeChatId];

  return (
    <div className="app">
      <Sidebar chats={chats} activeChatId={activeChatId} onSelect={setActiveChatId} onNewChat={createChat} />
      <div className="chat-column">
        <header className="app-header">mcp-shell</header>
        <main className="app-main">
          {messages.length === 0 ? <EmptyState onPick={handleSend} /> : <ChatThread messages={messages} />}
        </main>
        <ChatInput onSend={handleSend} disabled={sending} />
      </div>
    </div>
  );
}
