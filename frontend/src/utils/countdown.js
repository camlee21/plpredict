import { useEffect, useState } from "react";

// Under this long to go, the deadline is shown as urgent.
const URGENT_MS = 24 * 60 * 60 * 1000;

// A ticking "time until" for a deadline: { text, urgent }, or null when
// there's no deadline.
export function useCountdown(deadline) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!deadline) return null;
  const diffMs = new Date(deadline).getTime() - now;
  if (diffMs <= 0) return { text: "Locked", urgent: false };

  const totalSeconds = Math.floor(diffMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const text = days > 0 ? `${days}d ${hours}h ${minutes}m` : `${hours}h ${minutes}m ${seconds}s`;
  return { text, urgent: diffMs < URGENT_MS };
}
