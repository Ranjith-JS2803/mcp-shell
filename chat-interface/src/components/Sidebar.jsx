export default function Sidebar({ chats, activeChatId, onSelect, onNewChat }) {
  return (
    <aside className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        + New chat
      </button>
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
