import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../api/client";
import { api, blockingError, queryKeys, useApi } from "../api/queries";
import ConfirmDialog from "../components/ConfirmDialog";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../utils/format";

const USERNAME_MAX_LENGTH = 16;
// Mirrors backend/leagues/views.py's MAX_LEAGUES_PER_USER.
const MAX_LEAGUES = 10;

export default function ProfilePage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();

  const queryClient = useQueryClient();
  // Shared with the Home, Predict and Leagues pages, so these are usually
  // already cached by the time you get here.
  const historyQuery = useApi(api.history());
  const leaguesQuery = useApi(api.myLeagues());
  const stats =
    historyQuery.data && leaguesQuery.data
      ? {
          overallPoints: historyQuery.data.overall_total,
          gameweeksPlayed: historyQuery.data.by_gameweek.length,
          leagueCount: leaguesQuery.data.length,
        }
      : undefined;
  const statsError = blockingError(historyQuery) || blockingError(leaguesQuery);

  const [username, setUsername] = useState(user.username);
  const [usernameSaving, setUsernameSaving] = useState(false);
  const [usernameError, setUsernameError] = useState("");
  const [usernameMessage, setUsernameMessage] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const handleUsernameSubmit = async (e) => {
    e.preventDefault();
    setUsernameError("");
    setUsernameMessage("");
    setUsernameSaving(true);
    try {
      const updated = await apiRequest("/api/auth/me/", { method: "PATCH", body: { username } });
      setUser(updated);
      setUsername(updated.username);
      // Your name appears in every league table you're in.
      queryClient.invalidateQueries({ queryKey: queryKeys.leagues, refetchType: "all" });
      setUsernameMessage("Username saved.");
    } catch (err) {
      setUsernameError(err.message);
    } finally {
      setUsernameSaving(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setPasswordError("");
    setPasswordMessage("");
    setPasswordSaving(true);
    try {
      await apiRequest("/api/auth/me/password/", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordMessage("Password changed.");
    } catch (err) {
      setPasswordError(err.message);
    } finally {
      setPasswordSaving(false);
    }
  };

  const cancelDelete = useCallback(() => {
    setConfirmingDelete(false);
    setDeleteError("");
  }, []);

  const handleDeleteAccount = async () => {
    setDeleteError("");
    setDeleting(true);
    try {
      await apiRequest("/api/auth/me/", { method: "DELETE" });
      logout();
      navigate("/login", { state: { message: "Your account has been successfully deleted." } });
    } catch (err) {
      setDeleteError(err.message);
      setDeleting(false);
    }
  };

  return (
    <>
      <PageHeader
        title={user.username}
        meta={[
          user.email,
          `Joined ${formatDate(user.date_joined)}`,
          user.has_usable_password_flag ? "Signs in with a password" : "Signs in with Google",
        ]}
      />

      <main className="page profile-page">
        {stats === undefined && !statsError && <LoadingIndicator label="Loading your stats..." />}
        {statsError && <div className="error-banner">{statsError}</div>}
        {stats && (
          <dl className="panel stat-row">
            <div className="stat">
              <dt>Career points</dt>
              <dd>{stats.overallPoints}</dd>
            </div>
            <div className="stat">
              <dt>Gameweeks scored</dt>
              <dd>{stats.gameweeksPlayed}</dd>
            </div>
            <div className="stat">
              <dt>Leagues joined</dt>
              <dd>
                {stats.leagueCount}
                <span className="stat-of">/{MAX_LEAGUES}</span>
              </dd>
            </div>
          </dl>
        )}

        <div className="section-head">
          <h2>Account settings</h2>
        </div>
        <div className="settings-grid">
          <form className="panel side-form" onSubmit={handleUsernameSubmit}>
            <h3>Username</h3>
            <label>
              Shown in league tables and used to log in
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                maxLength={USERNAME_MAX_LENGTH}
                required
              />
            </label>
            <p className="muted small">
              Up to {USERNAME_MAX_LENGTH} characters: letters, numbers and full stops, no spaces.
            </p>
            {usernameError && <div className="error-banner">{usernameError}</div>}
            {usernameMessage && <div className="success-banner">{usernameMessage}</div>}
            <button
              type="submit"
              className="primary"
              disabled={usernameSaving || !username || username === user.username}
            >
              {usernameSaving ? "Saving..." : "Save username"}
            </button>
          </form>

          {user.has_usable_password_flag && (
            <form className="panel side-form" onSubmit={handlePasswordSubmit}>
              <h3>Password</h3>
              <label>
                Current password
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <label>
                New password
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
              </label>
              {passwordError && <div className="error-banner">{passwordError}</div>}
              {passwordMessage && <div className="success-banner">{passwordMessage}</div>}
              <button type="submit" className="primary" disabled={passwordSaving || !currentPassword || !newPassword}>
                {passwordSaving ? "Saving..." : "Change password"}
              </button>
            </form>
          )}
        </div>

        <div className="danger-zone">
          <div>
            <h3>Delete account</h3>
            <p className="muted small">
              Permanently deletes your predictions, the leagues you created and your league
              memberships. This can't be undone.
            </p>
          </div>
          <button type="button" className="danger" onClick={() => setConfirmingDelete(true)}>
            Delete account
          </button>
        </div>

        {confirmingDelete && (
          <ConfirmDialog
            title="Delete your account?"
            confirmLabel="Delete account"
            busyLabel="Deleting..."
            busy={deleting}
            error={deleteError}
            onConfirm={handleDeleteAccount}
            onCancel={cancelDelete}
          >
            <p>
              This permanently deletes all your data - your predictions, any leagues you own, and your
              league memberships - and it can't be undone.
            </p>
          </ConfirmDialog>
        )}
      </main>
    </>
  );
}
