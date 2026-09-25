import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import { api, blockingError, forgetLeague, useApi, usePrefetchOnIntent } from "../api/queries";
import ConfirmDialog from "../components/ConfirmDialog";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import ScoringInfo from "../components/ScoringInfo";
import { useAuth } from "../context/AuthContext";

// What the league endpoint answers with when you're not (or no longer) a member.
const MEMBERS_ONLY_STATUSES = [401, 403, 404];

export default function LeaguePage() {
  const { publicId } = useParams();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const prefetchOnIntent = usePrefetchOnIntent();
  const query = useApi(api.league(publicId), { enabled: Boolean(user) });
  const league = query.data ?? null;
  // Checked even when there's a cached copy: if a re-check says you're no
  // longer in this league (you were removed, or it was deleted), the old
  // standings shouldn't keep showing.
  const membersOnly = (!authLoading && !user) || MEMBERS_ONLY_STATUSES.includes(query.error?.status);
  const error = blockingError(query, { ignoreStatus: MEMBERS_ONLY_STATUSES });
  const [copiedCode, setCopiedCode] = useState(false);
  const [confirmingLeave, setConfirmingLeave] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

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
      forgetLeague(queryClient, publicId);
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
      forgetLeague(queryClient, publicId);
    } catch (err) {
      setDeleteError(err.message);
      setDeleting(false);
    }
  };

  if (authLoading) return <div className="page-loading">Loading...</div>;

  if (membersOnly) {
    return (
      <main className="page">
        <div className="panel auth-required-card">
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
      </main>
    );
  }

  const back = (
    <Link to="/leagues" className="back-link">
      &larr; Leagues
    </Link>
  );

  if (error || !league) {
    return (
      <>
        <PageHeader title="League" back={back} />
        <main className="page">
          {error ? <div className="error-banner">{error}</div> : <LoadingIndicator label="Loading league..." />}
        </main>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={league.name}
        back={back}
        meta={[
          league.is_public ? "Public league" : "Private league",
          `${league.member_count} of ${league.max_members} members`,
          `Created by ${league.owner_username}`,
          league.starting_gameweek && `Scores count from Gameweek ${league.starting_gameweek}`,
        ]}
        actions={<ScoringInfo />}
      >
        {!league.is_public && (
          <div className="invite-code">
            <span>
              Invite code <strong>{league.code}</strong>
            </span>
            <button type="button" className="invite-copy" onClick={copyCode}>
              {copiedCode ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </PageHeader>

      <main className="page">
        <div className="table-wrap">
          <table className="standings-table">
            <thead>
              <tr>
                <th className="col-rank">Pos</th>
                <th>Player</th>
                <th className="col-num">{league.current_gameweek ? `GW${league.current_gameweek}` : "This GW"}</th>
                <th className="col-num">Total</th>
              </tr>
            </thead>
            <tbody>
              {league.standings.map((row) => (
                <tr key={row.user_id} className={row.user_id === user?.id ? "is-you" : undefined}>
                  <td className="col-rank">{row.rank_display}</td>
                  <td>
                    <Link
                      to={`/leagues/${publicId}/players/${row.user_id}`}
                      {...prefetchOnIntent(api.leagueMember(publicId, row.user_id))}
                    >
                      {row.username}
                    </Link>
                  </td>
                  {/* A dash, not 0, until a gameweek has actually counted for
                      them - someone who just joined hasn't scored nothing, they
                      haven't played yet. */}
                  <td className="col-num">{row.current_gameweek_counts ? row.current_gameweek_points : "-"}</td>
                  <td className="col-num col-total">{row.has_counted_gameweeks ? row.total_points : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="league-manage">
          {league.is_owner ? (
            <>
              <p className="muted small">You created this league.</p>
              <button className="danger" onClick={() => setConfirmingDelete(true)}>
                Delete league
              </button>
            </>
          ) : (
            <button className="secondary" onClick={() => setConfirmingLeave(true)}>
              Leave league
            </button>
          )}
        </div>

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
              Your predictions and points stay with your account. If you rejoin, this league's total
              starts again from the gameweek you rejoin.
            </p>
          </ConfirmDialog>
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
              Nobody's predictions or points are lost. Those belong to each player's account, not to
              the league.
            </p>
          </ConfirmDialog>
        )}
      </main>
    </>
  );
}
