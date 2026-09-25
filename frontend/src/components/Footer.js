import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="site-footer">
      <span>PL Predict</span>
      <Link to="/privacy">Privacy policy</Link>
    </footer>
  );
}
