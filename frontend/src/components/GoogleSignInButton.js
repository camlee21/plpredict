import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export default function GoogleSignInButton({ onError }) {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const divRef = useRef(null);

  useEffect(() => {
    if (!CLIENT_ID) return;

    // The Google Identity Services script (loaded via <script async defer>
    // in index.html) may not have finished loading yet when this effect
    // first runs - retry until it has, rather than silently giving up.
    let cancelled = false;
    let attempts = 0;

    const tryRender = () => {
      if (cancelled || !divRef.current) return;
      if (!window.google?.accounts?.id) {
        if (attempts++ < 50) setTimeout(tryRender, 100);
        return;
      }

      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: async (response) => {
          try {
            await loginWithGoogle(response.credential);
            navigate("/");
          } catch (err) {
            onError?.(err.message);
          }
        },
      });
      window.google.accounts.id.renderButton(divRef.current, {
        theme: "outline",
        size: "large",
        width: 280,
      });
    };
    tryRender();

    return () => {
      cancelled = true;
    };
  }, [loginWithGoogle, onError, navigate]);

  if (!CLIENT_ID) {
    return (
      <p className="muted small">
        Google sign-in isn't configured (set REACT_APP_GOOGLE_CLIENT_ID).
      </p>
    );
  }

  return <div ref={divRef} className="google-signin-wrapper" />;
}
