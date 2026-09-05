import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";

export default function LeaguePage() {
  const { id } = useParams();
  const [league, setLeague] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiRequest(`/api/leagues/${id}/`)
      .then(setLeague)
      .catch((err) => setError(err.message));
  }, [id]);

  const copyCode = () => {
    navigator.clipboard?.writeText(league.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (error) return <div className="page error-banner">{error}</div>;
  if (!league) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <Link to="/" className="back-link">
        &larr; All leagues
      </Link>
      <h1>{league.name}</h1>
      <div className="league-code-banner card">
        <span>
          Invite code: <strong>{league.code}</strong>
        </span>
        <button className="secondary" onClick={copyCode}>
          {copied ? "Copied!" : "Copy code"}
        </button>
      </div>

      <h2>Standings</h2>
      <table className="standings-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Player</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {league.standings.map((row, index) => (
            <tr key={row.user_id}>
              <td>{index + 1}</td>
              <td>{row.username}</td>
              <td>{row.total_points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
