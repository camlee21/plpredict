import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import GoogleSignInButton from "../components/GoogleSignInButton";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice] = useState(location.state?.message ?? "");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(usernameOrEmail, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout>
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Welcome back</h1>
        {notice && <div className="success-banner">{notice}</div>}
        {error && <div className="error-banner">{error}</div>}
        <label>
          Username or email
          <input
            value={usernameOrEmail}
            onChange={(e) => setUsernameOrEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? "Logging in..." : "Log in"}
        </button>

        <div className="divider"><span>or</span></div>
        <GoogleSignInButton onError={setError} />

        <p className="auth-switch">
          No account yet? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
