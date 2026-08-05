const EXAMPLES = [
  "Show me revenue by region",
  "Show me a table of orders from the North region",
  "Generate a sales report for this quarter",
];

export default function EmptyState({ onPick }) {
  return (
    <div className="empty-state">
      <p>Ask about the e-commerce dataset.</p>
      <div className="example-chips">
        {EXAMPLES.map((example) => (
          <button key={example} onClick={() => onPick(example)}>
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
