import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatThread({ messages }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-thread">
      {messages.map((m) => (
        <MessageBubble key={m.message_id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
