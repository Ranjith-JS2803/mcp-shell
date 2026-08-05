import ArtifactFrame from "./ArtifactFrame.jsx";

export default function MessageBubble({ message }) {
  const { role, status, text, artifact } = message;

  return (
    <div className={`bubble-row ${role}`}>
      <div className={`bubble ${role}`}>
        {status === "pending" ? (
          <span className="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </span>
        ) : (
          <>
            {text && <p className="bubble-text">{text}</p>}
            {artifact?.template_html && (
              <ArtifactFrame templateHtml={artifact.template_html} data={artifact.data} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
