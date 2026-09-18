export default function LoadingIndicator({ label = "Loading..." }) {
  return (
    <div className="loading-indicator" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
