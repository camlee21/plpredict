import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../utils/format";

const USERNAME_MAX_LENGTH = 16;
// Mirrors backend/leagues/views.py's MAX_LEAGUES_PER_USER.
const MAX_LEAGUES = 10;

export default function ProfilePage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] = useState(undefined);
  const [statsError, setStatsError] = useState("");

  const [username, setUsername] = useState(user.username);
  const [usernameSaving, setUsernameSaving] = useState(false);
  const [usernameError, setUsernameError] = useState("");
  const [usernameMessage, setUsernameMessage] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");

  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    Promise.all([apiRequest("/api/predictions/history/"), apiRequest("/api/leagues/")])
      .then(([history, leagues]) => {
        setStats({
          overallPoints: history.overall_total,
          gameweeksPlayed: history.by_gameweek.length,
          leagueCount: leagues.length,
        });
      })
      .catch((err) => setStatsError(err.message));
  }, []);

  const handleUsernameSubmit = async (e) => {
    e.preventDefault();
    setUsernameError("");
    setUsernameMessage("");
    setUsernameSaving(true);
    try {
      const updated = await apiRequest("/api/auth/me/", { method: "PATCH", body: { username } });
      setUser(updated);
      setUsername(updated.username);
      setUsernameMessage("Username updated!");
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
      setPasswordMessage("Password updated!");
    } catch (err) {
      setPasswordError(err.message);
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    const confirmed = window.confirm(
      "Delete your account? This will permanently delete all your data - your predictions, " +
        "any leagues you own, and your league memberships - and cannot be undone."
    );
    if (!confirmed) return;

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
    <div className="page profile-page">
      <h1>Profile</h1>

      <div className="card">
        <h2>Account</h2>
        <p className="muted">Email: {user.email}</p>
        <p className="muted">Member since: {formatDate(user.date_joined)}</p>
        <p className="muted">
          {user.has_usable_password_flag ? "You sign in with a username/email and password." : "You sign in with Google."}
        </p>
      </div>

      <div className="card">
        <h2>Your stats</h2>
        {stats === undefined && !statsError && <p>Loading...</p>}
        {statsError && <div className="error-banner">{statsError}</div>}
        {stats && (
          <div className="profile-stats-row">
            <div className="profile-stat">
              <div className="stat-value">{stats.overallPoints}</div>
              <div className="muted small">Career points</div>
            </div>
            <div className="profile-stat">
              <div className="stat-value">{stats.gameweeksPlayed}</div>
              <div className="muted small">Gameweeks scored</div>
            </div>
            <div className="profile-stat">
              <div className="stat-value">
                {stats.leagueCount}/{MAX_LEAGUES}
              </div>
              <div className="muted small">
                <Link to="/leagues">Leagues joined</Link>
              </div>
            </div>
          </div>
        )}
      </div>

      <form className="card" onSubmit={handleUsernameSubmit}>
        <h2>Username</h2>
        <label>
          Shown in league tables and used to log in.
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            maxLength={USERNAME_MAX_LENGTH}
            required
          />
        </label>
        <p className="muted small">
          Up to {USERNAME_MAX_LENGTH} characters - letters, numbers and periods only, no spaces.
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
        <form className="card" onSubmit={handlePasswordSubmit}>
          <h2>Change password</h2>
          <label>
            Current password
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
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

      <div className="card danger-zone">
        <h2>Delete account</h2>
        <p className="muted">
          Permanently delete your account and all your data - predictions, leagues you own, and
          league memberships. This cannot be undone.
        </p>
        {deleteError && <div className="error-banner">{deleteError}</div>}
        <button type="button" className="danger" onClick={handleDeleteAccount} disabled={deleting}>
          {deleting ? "Deleting..." : "Delete account"}
        </button>
      </div>
    </div>
  );
}
