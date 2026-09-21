import { Link, NavLink, useNavigate } from "react-router-dom";
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
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/leagues">Leagues</NavLink>
        <NavLink to="/fixtures">Fixtures</NavLink>
        <NavLink to="/predict">Predict</NavLink>
      </div>
      <div className="nav-account">
        <span className="nav-divider" aria-hidden="true" />
        <Link to="/profile" className="nav-user">
          {user.username}
        </Link>
        <button className="link-button" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </nav>
  );
}
