import { useRef } from "react";

/** One WebSocket identity per browser tab, shared across every chat in
 * that tab — persisted so a page refresh doesn't open a new connection
 * history has to reconcile. */
export function useSocketId() {
  const socketId = useRef(
    (() => {
      let value = sessionStorage.getItem("mcp-shell-socket-id");
      if (!value) {
        value = crypto.randomUUID();
        sessionStorage.setItem("mcp-shell-socket-id", value);
      }
      return value;
    })(),
  ).current;
  return socketId;
}
