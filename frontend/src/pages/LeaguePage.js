import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function LeaguePage() {
  const { publicId } = useParams();
  const { user, loading: authLoading } = useAuth();
  const [league, setLeague] = useState(null);
  const [membersOnly, setMembersOnly] = useState(false);
  const [error, setError] = useState("");
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      setMembersOnly(true);
      return;
    }

    apiRequest(`/api/leagues/${publicId}/`)
      .then(setLeague)
      .catch((err) => {
        if (err.status === 401 || err.status === 403 || err.status === 404) {
          setMembersOnly(true);
        } else {
          setError(err.message);
        }
      });
  }, [publicId, user, authLoading]);

  const shareLink = `${window.location.origin}/leagues/${publicId}`;

  const copyCode = () => {
    navigator.clipboard?.writeText(league.code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 1500);
  };

  const copyLink = () => {
    navigator.clipboard?.writeText(shareLink);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 1500);
  };

  if (authLoading) return <div className="page-loading">Loading...</div>;

  if (membersOnly) {
    return (
      <div className="page">
        <div className="card auth-required-card">
          <h1>Members only</h1>
          <p>You need to be a member to see this league's details.</p>
          {user ? (
            <Link to="/" className="primary-link">
              Back to your leagues
            </Link>
          ) : (
            <Link to="/login" className="primary-link">
              Log in
            </Link>
          )}
        </div>
      </div>
    );
  }

  if (error) return <div className="page error-banner">{error}</div>;
  if (!league) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <Link to="/" className="back-link">
        &larr; All leagues
      </Link>
      <h1>{league.name}</h1>
      <p className="muted">
        {league.is_public ? "Public league" : "Private league"} &middot; {league.member_count}/
        {league.max_members} members
      </p>

      <div className="league-code-banner card">
        <span>Shareable link:</span>
        <code className="share-link">{shareLink}</code>
        <button className="secondary" onClick={copyLink}>
          {copiedLink ? "Copied!" : "Copy link"}
        </button>
      </div>

      {!league.is_public && (
        <div className="league-code-banner card">
          <span>
            Invite code: <strong>{league.code}</strong>
          </span>
          <button className="secondary" onClick={copyCode}>
            {copiedCode ? "Copied!" : "Copy code"}
          </button>
        </div>
      )}

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
