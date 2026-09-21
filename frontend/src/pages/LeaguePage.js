import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import ScoringInfo from "../components/ScoringInfo";
import { useAuth } from "../context/AuthContext";

export default function LeaguePage() {
  const { publicId } = useParams();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [league, setLeague] = useState(null);
  const [membersOnly, setMembersOnly] = useState(false);
  const [error, setError] = useState("");
  const [copiedCode, setCopiedCode] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState("");

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

  const copyCode = () => {
    navigator.clipboard?.writeText(league.code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 1500);
  };

  const handleLeave = async () => {
    if (!window.confirm(`Leave "${league.name}"? You'll need to rejoin (by code, or publicly if it's public) to get back in.`)) {
      return;
    }
    setLeaveError("");
    setLeaving(true);
    try {
      await apiRequest(`/api/leagues/${publicId}/leave/`, { method: "POST" });
      navigate("/leagues");
    } catch (err) {
      setLeaveError(err.message);
      setLeaving(false);
    }
  };

  if (authLoading) return <div className="page-loading">Loading...</div>;

  if (membersOnly) {
    return (
      <div className="page">
        <div className="card auth-required-card">
          <h1>Members only</h1>
          <p>You need to be a member to see this league's details.</p>
          {user ? (
            <Link to="/leagues" className="primary-link">
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
      <Link to="/leagues" className="back-link">
        &larr; All leagues
      </Link>
      <h1>{league.name}</h1>
      <p className="muted">
        {league.is_public ? "Public league" : "Private league"} &middot; {league.member_count}/
        {league.max_members} members &middot; Created by {league.owner_username}
      </p>
      {league.starting_gameweek && (
        <p className="muted">Scores count from Gameweek {league.starting_gameweek} onwards.</p>
      )}

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

      {!league.is_owner && (
        <div className="league-leave-row">
          {leaveError && <div className="error-banner">{leaveError}</div>}
          <button className="secondary" onClick={handleLeave} disabled={leaving}>
            {leaving ? "Leaving..." : "Leave league"}
          </button>
        </div>
      )}

      <div className="heading-row">
        <h2>Standings</h2>
        <ScoringInfo />
      </div>
      <table className="standings-table">
        <thead>
          <tr>
            <th>Pos</th>
            <th>Player</th>
            <th>{league.current_gameweek ? `GW${league.current_gameweek}` : "Current GW"}</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {league.standings.map((row) => (
            <tr key={row.user_id}>
              <td>{row.rank_display}</td>
              <td>
                <Link to={`/leagues/${publicId}/players/${row.user_id}`}>{row.username}</Link>
              </td>
              {/* A dash, not 0, until a gameweek has actually counted for
                  them - someone who just joined hasn't scored nothing, they
                  haven't played yet. */}
              <td>{row.current_gameweek_counts ? row.current_gameweek_points : "-"}</td>
              <td>{row.has_counted_gameweeks ? row.total_points : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
