import { useLayoutEffect, useRef, useState } from "react";

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  // Auto-grows with content instead of staying a fixed single-row box —
  // without this, typed text just scrolls out of view once it wraps.
  // Uncapped: it just keeps growing, so no internal scrollbar ever appears.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="chat-input">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about revenue, orders, products..."
        rows={1}
      />
      <button onClick={submit} disabled={disabled || !value.trim()}>
        Send
      </button>
    </div>
  );
}
