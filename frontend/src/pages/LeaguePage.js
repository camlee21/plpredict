import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import ConfirmDialog from "../components/ConfirmDialog";
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
  const [confirmingLeave, setConfirmingLeave] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

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

  const cancelLeave = useCallback(() => {
    setConfirmingLeave(false);
    setLeaveError("");
  }, []);

  const handleLeave = async () => {
    setLeaveError("");
    setLeaving(true);
    try {
      await apiRequest(`/api/leagues/${publicId}/leave/`, { method: "POST" });
      navigate("/leagues", { state: { message: `You left "${league.name}".` } });
    } catch (err) {
      setLeaveError(err.message);
      setLeaving(false);
    }
  };

  const cancelDelete = useCallback(() => {
    setConfirmingDelete(false);
    setDeleteError("");
  }, []);

  const handleDelete = async () => {
    setDeleteError("");
    setDeleting(true);
    try {
      await apiRequest(`/api/leagues/${publicId}/`, { method: "DELETE" });
      navigate("/leagues", { state: { message: `"${league.name}" has been deleted.` } });
    } catch (err) {
      setDeleteError(err.message);
      setDeleting(false);
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
          <button className="secondary" onClick={() => setConfirmingLeave(true)}>
            Leave league
          </button>
        </div>
      )}

      {confirmingLeave && (
        <ConfirmDialog
          title={`Leave "${league.name}"?`}
          confirmLabel="Leave league"
          busyLabel="Leaving..."
          busy={leaving}
          error={leaveError}
          onConfirm={handleLeave}
          onCancel={cancelLeave}
        >
          <p>
            You'll drop off the standings and need to rejoin{" "}
            {league.is_public ? "from the public league list" : "with the invite code"} to get back
            in.
          </p>
          <p className="muted">
            Your predictions and points stay with your account - if you rejoin, this league's total
            starts again from the gameweek you rejoin.
          </p>
        </ConfirmDialog>
      )}

      {league.is_owner && (
        <div className="league-leave-row">
          <button className="danger" onClick={() => setConfirmingDelete(true)}>
            Delete league
          </button>
        </div>
      )}

      {confirmingDelete && (
        <ConfirmDialog
          title={`Delete "${league.name}"?`}
          confirmLabel="Delete league"
          busyLabel="Deleting..."
          busy={deleting}
          error={deleteError}
          onConfirm={handleDelete}
          onCancel={cancelDelete}
        >
          <p>
            This removes the league and its standings for all {league.member_count}{" "}
            {league.member_count === 1 ? "member" : "members"}, and it can't be undone.
          </p>
          <p className="muted">
            Nobody's predictions or points are lost - those belong to each player's account, not to
            the league.
          </p>
        </ConfirmDialog>
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
