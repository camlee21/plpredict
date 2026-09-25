// The purple band at the top of every page. It carries straight on from the
// navbar, and its angled bottom edge is where the page's content begins.
// `meta` is a list of short facts shown under the title (falsy ones skipped).
export default function PageHeader({ title, back, meta, actions, children }) {
  const facts = (meta ?? []).filter(Boolean);
  return (
    <header className="masthead">
      <div className="masthead-inner">
        {back}
        <div className="masthead-title-row">
          <h1>{title}</h1>
          {actions && <div className="masthead-actions">{actions}</div>}
        </div>
        {facts.length > 0 && (
          <ul className="masthead-meta">
            {facts.map((fact, index) => (
              <li key={index}>{fact}</li>
            ))}
          </ul>
        )}
        {children}
      </div>
    </header>
  );
}
