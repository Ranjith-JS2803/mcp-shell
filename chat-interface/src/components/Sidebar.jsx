export default function Sidebar({ chats, activeChatId, onSelect, onNewChat, onCollapse }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <button className="new-chat-btn" onClick={onNewChat}>
          + New chat
        </button>
        <button className="collapse-btn" onClick={onCollapse} title="Close sidebar" aria-label="Close sidebar">
          «
        </button>
      </div>
      <div className="chat-list">
        {chats.map((chat) => (
          <button
            key={chat.chat_id}
            className={`chat-list-item${chat.chat_id === activeChatId ? " active" : ""}`}
            onClick={() => onSelect(chat.chat_id)}
            title={chat.title}
          >
            {chat.title}
          </button>
        ))}
      </div>
    </aside>
  );
}
