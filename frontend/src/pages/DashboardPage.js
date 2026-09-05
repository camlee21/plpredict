import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api/client";

export default function DashboardPage() {
  const [leagues, setLeagues] = useState(null);
  const [error, setError] = useState("");
  const [newLeagueName, setNewLeagueName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);

  const loadLeagues = async () => {
    try {
      const data = await apiRequest("/api/leagues/");
      setLeagues(data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadLeagues();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest("/api/leagues/", { method: "POST", body: { name: newLeagueName } });
      setNewLeagueName("");
      await loadLeagues();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest("/api/leagues/join/", { method: "POST", body: { code: joinCode } });
      setJoinCode("");
      await loadLeagues();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h1>Your leagues</h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="league-actions">
        <form className="card" onSubmit={handleCreate}>
          <h2>Create a league</h2>
          <label>
            League name
            <input
              value={newLeagueName}
              onChange={(e) => setNewLeagueName(e.target.value)}
              placeholder="e.g. Office Sweepstake"
              required
            />
          </label>
          <button className="primary" type="submit" disabled={busy}>
            Create
          </button>
        </form>

        <form className="card" onSubmit={handleJoin}>
          <h2>Join a league</h2>
          <label>
            6-character code
            <input
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder="e.g. 7GH4LP"
              maxLength={6}
              required
            />
          </label>
          <button className="primary" type="submit" disabled={busy}>
            Join
          </button>
        </form>
      </div>

      <h2>Leagues you're in</h2>
      {leagues === null && <p>Loading...</p>}
      {leagues && leagues.length === 0 && <p className="muted">You haven't joined any leagues yet.</p>}
      <div className="league-grid">
        {leagues?.map((league) => (
          <Link to={`/leagues/${league.id}`} key={league.id} className="card league-card">
            <h3>{league.name}</h3>
            <p className="muted">Code: {league.code}</p>
            <p className="muted">{league.member_count} member{league.member_count === 1 ? "" : "s"}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
