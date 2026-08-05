import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../api/gatewayClient.js";

/** Outbound-only from gateway's side — this hook only ever listens and
 * reconnects; it never sends a request over the socket. */
export function useWebSocket(socketId, onMessage) {
  const [connected, setConnected] = useState(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let socket;
    let retryTimer;
    let closedByEffect = false;

    function connect() {
      socket = new WebSocket(wsUrl(socketId));

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closedByEffect) retryTimer = setTimeout(connect, 2000);
      };
      socket.onerror = () => socket.close();
      socket.onmessage = (event) => {
        try {
          onMessageRef.current(JSON.parse(event.data));
        } catch {
          // malformed frame — ignore
        }
      };
    }

    connect();

    return () => {
      closedByEffect = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, [socketId]);

  return connected;
}
