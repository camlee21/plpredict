const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function ordinal(day) {
  if (day % 100 >= 11 && day % 100 <= 13) return `${day}th`;
  switch (day % 10) {
    case 1: return `${day}st`;
    case 2: return `${day}nd`;
    case 3: return `${day}rd`;
    default: return `${day}th`;
  }
}

// e.g. "30th May 2026"
export function formatDate(value) {
  const date = new Date(value);
  return `${ordinal(date.getDate())} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

// e.g. "11:30PM"
export function formatTime(value) {
  const date = new Date(value);
  const hours24 = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const hours12 = hours24 % 12 || 12;
  return `${hours12}:${minutes}${hours24 >= 12 ? "PM" : "AM"}`;
}

// e.g. "30th May 2026, 11:30PM"
export function formatDateTime(value) {
  return `${formatDate(value)}, ${formatTime(value)}`;
}
