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
  const { chats, activeChatId, setActiveChatId, createChat, renameChat, removeChat, isFreshChat } = useChatList();
  const [messagesByChat, setMessagesByChat] = useState({});
  const [sendingByChat, setSendingByChat] = useState({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("mcp-shell-sidebar-collapsed") === "1",
  );
  const loadedChatsRef = useRef(new Set());
  const creatingChatRef = useRef(false);
  const titleBuffers = useRef({}); // chat_id -> accumulated title text while streaming

  // message_id -> { chatId, queue: string, timer: number|null, finalResponse: object|null }
  const revealState = useRef({});

  useEffect(() => {
    localStorage.setItem("mcp-shell-sidebar-collapsed", sidebarCollapsed ? "1" : "0");
  }, [sidebarCollapsed]);

  // Lazily fetch history the first time a chat is opened. If a chat that
  // existed before this session (i.e. persisted in localStorage from a
  // prior visit) comes back with no history at all, the backend has
  // nothing for it — most likely its Redis data is gone — so prune it
  // from the sidebar instead of keeping a permanently-empty entry.
  // A chat created in this session is exempt: it legitimately has no
  // history yet until its first message is sent.
  useEffect(() => {
    if (!activeChatId || loadedChatsRef.current.has(activeChatId)) return;
    loadedChatsRef.current.add(activeChatId);
    const chatId = activeChatId;
    getHistory(chatId)
      .then((history) => {
        if (history.length) {
          setMessagesByChat((prev) => ({ ...prev, [chatId]: historyToMessages(history) }));
        } else if (!isFreshChat(chatId)) {
          removeChat(chatId);
          setMessagesByChat((prev) => {
            const next = { ...prev };
            delete next[chatId];
            return next;
          });
          // Release activeChatId if it's still pointing at the chat we
          // just removed — otherwise the "no active chat" fallback effect
          // never fires (its guard sees a still-truthy, now-orphaned id)
          // and the UI is stuck showing an empty thread for nothing.
          setActiveChatId((current) => (current === chatId ? null : current));
        }
      })
      .catch(() => {
        // gateway briefly unreachable — don't prune on a network blip
      });
  }, [activeChatId, isFreshChat, removeChat, setActiveChatId]);

  // Whenever there's no active chat — first-ever visit, or one was just
  // pruned away — fall back to another existing chat, or start a fresh
  // one if there's truly nothing left. The ref guard (checked and set
  // synchronously, not via state) is what makes this safe under
  // StrictMode's double-invoke: the second invocation sees it already
  // set and skips, so createChat() can never fire twice for one gap.
  useEffect(() => {
    if (activeChatId) {
      creatingChatRef.current = false;
      return;
    }
    if (chats.length > 0) {
      setActiveChatId(chats[0].chat_id);
      return;
    }
    if (creatingChatRef.current) return;
    creatingChatRef.current = true;
    createChat();
  }, [activeChatId, chats, createChat, setActiveChatId]);

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
      if (event.event === "title_chunk") {
        const chatId = event.chat_id;
        const buffered = (titleBuffers.current[chatId] || "") + event.text;
        titleBuffers.current[chatId] = buffered;
        renameChat(chatId, buffered);
        return;
      }

      if (event.event === "title_done") {
        renameChat(event.chat_id, event.title);
        delete titleBuffers.current[event.chat_id];
        return;
      }

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
    [ensureRevealTimer, finalizeMessage, renameChat],
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
      await postChat({ chatId, messageId, socketId, userQuery, isFirstMessage });
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
      {sidebarCollapsed ? (
        <button
          className="sidebar-expand-btn"
          onClick={() => setSidebarCollapsed(false)}
          title="Open sidebar"
          aria-label="Open sidebar"
        >
          »
        </button>
      ) : (
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelect={setActiveChatId}
          onNewChat={createChat}
          onCollapse={() => setSidebarCollapsed(true)}
        />
      )}
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
