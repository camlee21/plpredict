import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api/client";

const MAX_MEMBERS_OPTIONS = [4, 8, 16, 32, 64, 128];
const LEAGUE_NAME_MAX_LENGTH = 32;

export default function LeaguesPage() {
  const [leagues, setLeagues] = useState(null);
  const [publicLeagues, setPublicLeagues] = useState(null);
  const [error, setError] = useState("");
  const [newLeagueName, setNewLeagueName] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [maxMembers, setMaxMembers] = useState(8);
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [joiningId, setJoiningId] = useState(null);

  const [search, setSearch] = useState("");
  const [browseFilter, setBrowseFilter] = useState("recent");

  const loadMyLeagues = useCallback(async () => {
    try {
      setLeagues(await apiRequest("/api/leagues/"));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const loadPublicLeagues = useCallback(async () => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    params.set("filter", browseFilter);
    const query = params.toString();

    try {
      setPublicLeagues(await apiRequest(`/api/leagues/browse/${query ? `?${query}` : ""}`));
    } catch (err) {
      setError(err.message);
    }
  }, [search, browseFilter]);

  useEffect(() => {
    loadMyLeagues();
  }, [loadMyLeagues]);

  useEffect(() => {
    const timeout = setTimeout(loadPublicLeagues, 300);
    return () => clearTimeout(timeout);
  }, [loadPublicLeagues]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest("/api/leagues/", {
        method: "POST",
        body: { name: newLeagueName, is_public: isPublic, max_members: maxMembers },
      });
      setNewLeagueName("");
      setIsPublic(true);
      setMaxMembers(8);
      await Promise.all([loadMyLeagues(), loadPublicLeagues()]);
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
      await Promise.all([loadMyLeagues(), loadPublicLeagues()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleJoinPublic = async (publicId) => {
    setError("");
    setJoiningId(publicId);
    try {
      await apiRequest(`/api/leagues/${publicId}/join/`, { method: "POST" });
      await Promise.all([loadMyLeagues(), loadPublicLeagues()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setJoiningId(null);
    }
  };

  return (
    <div className="page">
      <h1>Leagues</h1>
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
              maxLength={LEAGUE_NAME_MAX_LENGTH}
              required
            />
          </label>
          <label>
            Max members
            <select value={maxMembers} onChange={(e) => setMaxMembers(Number(e.target.value))}>
              {MAX_MEMBERS_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Visibility
            <select value={isPublic ? "public" : "private"} onChange={(e) => setIsPublic(e.target.value === "public")}>
              <option value="public">Public (listed for anyone to browse and join)</option>
              <option value="private">Private (join by invite code only)</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={busy}>
            Create
          </button>
        </form>

        <form className="card" onSubmit={handleJoin}>
          <h2>Join a private league</h2>
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

      <h2>Your leagues</h2>
      {leagues === null && <p>Loading...</p>}
      {leagues && leagues.length === 0 && <p className="muted">You haven't joined any leagues yet.</p>}
      {leagues && leagues.length > 0 && (
        <div className="league-row-list">
          {leagues.map((league) => (
            <div className="league-row" key={league.public_id}>
              <span className="league-row-name">{league.name}</span>
              <span className="league-row-detail muted">{league.is_public ? "Public" : "Private"}</span>
              <span className="league-row-detail muted">
                {league.member_count}/{league.max_members}
              </span>
              <span className="league-row-detail muted">{league.rank_display}</span>
              <Link to={`/leagues/${league.public_id}`} className="league-row-action">
                View league
              </Link>
            </div>
          ))}
        </div>
      )}

      <h2>Browse public leagues</h2>
      <div className="browse-filters">
        <label>
          Search by name
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="e.g. Office"
          />
        </label>
        <label>
          Filter by
          <select value={browseFilter} onChange={(e) => setBrowseFilter(e.target.value)}>
            <option value="recent">Recent</option>
            <option value="capacity_desc">Capacity (High-Low)</option>
            <option value="capacity_asc">Capacity (Low-High)</option>
          </select>
        </label>
      </div>

      {publicLeagues === null && <p>Loading...</p>}
      {publicLeagues && publicLeagues.length === 0 && (
        <p className="muted">No public leagues match your filters.</p>
      )}
      {publicLeagues && publicLeagues.length > 0 && (
        <div className="league-row-list">
          {publicLeagues.map((league) => (
            <div className="league-row" key={league.public_id}>
              <span className="league-row-name">{league.name}</span>
              <span className="league-row-detail muted">
                {league.member_count}/{league.max_members}
              </span>
              <span className="league-row-detail muted">
                {league.starting_gameweek ? `GW${league.starting_gameweek}` : "-"}
              </span>
              {league.is_member ? (
                <Link to={`/leagues/${league.public_id}`} className="league-row-action">
                  View league
                </Link>
              ) : (
                <button
                  className="league-row-action"
                  disabled={league.is_full || joiningId === league.public_id}
                  onClick={() => handleJoinPublic(league.public_id)}
                >
                  {league.is_full ? "Full" : joiningId === league.public_id ? "Joining..." : "Join"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
