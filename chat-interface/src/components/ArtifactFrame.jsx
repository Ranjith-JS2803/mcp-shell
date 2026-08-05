import { useEffect, useRef } from "react";
import { getResource } from "../api/gatewayClient.js";

/** Sandboxed, self-contained — never a src URL, data goes in via
 * postMessage after load, never baked into the srcdoc. */
export default function ArtifactFrame({ templateHtml, data }) {
  const iframeRef = useRef(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    function hydrate() {
      iframe.contentWindow?.postMessage({ type: "hydrate", data }, "*");
    }

    async function handleMessage(event) {
      if (event.source !== iframe.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;
      if (event.data.type !== "request_data") return;

      try {
        const { data: page } = await getResource(event.data.source);
        iframe.contentWindow?.postMessage({ type: "append", data: page }, "*");
      } catch {
        // best-effort — the template just won't get its next page
      }
    }

    iframe.addEventListener("load", hydrate);
    window.addEventListener("message", handleMessage);
    return () => {
      iframe.removeEventListener("load", hydrate);
      window.removeEventListener("message", handleMessage);
    };
  }, [data]);

  return (
    <iframe
      ref={iframeRef}
      sandbox="allow-scripts"
      srcDoc={templateHtml}
      title="artifact"
      className="artifact-frame"
    />
  );
}
