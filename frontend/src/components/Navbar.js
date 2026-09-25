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
      {/* On phones this becomes a tab bar fixed to the bottom of the screen. */}
      <div className="nav-links">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/predict">Predict</NavLink>
        <NavLink to="/leagues">Leagues</NavLink>
        <NavLink to="/fixtures">Fixtures</NavLink>
      </div>
      <div className="nav-account">
        <NavLink to="/profile" className="nav-user">
          {user.username}
        </NavLink>
        <button className="link-button" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </nav>
  );
}
