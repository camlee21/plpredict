import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="navbar">
      <Link to="/" className="brand">
        PL Predict
      </Link>
      <div className="nav-links">
        <Link to="/">Home</Link>
        <Link to="/leagues">Leagues</Link>
        <Link to="/predict">Predict</Link>
        <span className="nav-user">{user.username}</span>
        <button className="link-button" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </nav>
  );
}
