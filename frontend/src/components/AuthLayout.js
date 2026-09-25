// Login and register: the brand on a purple panel beside (or, on phones,
// above) the form.
export default function AuthLayout({ children }) {
  return (
    <div className="auth-page">
      <div className="auth-intro">
        <span className="auth-wordmark">PL Predict</span>
        <p>
          Predict the score of every Premier League match, then see where you finish against your
          friends.
        </p>
      </div>
      <div className="auth-form-side">{children}</div>
    </div>
  );
}
