import { useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";

const CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export default function GoogleSignInButton({ onError }) {
  const { loginWithGoogle } = useAuth();
  const divRef = useRef(null);

  useEffect(() => {
    if (!CLIENT_ID || !window.google || !divRef.current) return;

    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: async (response) => {
        try {
          await loginWithGoogle(response.credential);
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
  }, [loginWithGoogle, onError]);

  if (!CLIENT_ID) {
    return (
      <p className="muted small">
        Google sign-in isn't configured (set REACT_APP_GOOGLE_CLIENT_ID).
      </p>
    );
  }

  return <div ref={divRef} />;
}
