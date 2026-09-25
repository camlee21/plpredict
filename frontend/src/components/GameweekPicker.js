function optionLabel(gw) {
  return `Gameweek ${gw.number}${gw.lifecycle === "current" ? " (current)" : ""}`;
}

// A gameweek dropdown with previous/next steppers either side, since moving
// one week at a time is the usual thing to do.
export default function GameweekPicker({ gameweeks, selected, onChange }) {
  const index = gameweeks.findIndex((gw) => gw.number === selected);
  const previous = index > 0 ? gameweeks[index - 1] : null;
  const next = index !== -1 && index < gameweeks.length - 1 ? gameweeks[index + 1] : null;

  return (
    <div className="gw-picker">
      <button
        type="button"
        className="gw-step"
        aria-label="Previous gameweek"
        disabled={!previous}
        onClick={() => onChange(previous.number)}
      >
        <span aria-hidden="true">&#8249;</span>
      </button>
      <label className="gw-select">
        <span className="visually-hidden">Gameweek</span>
        <select value={selected ?? ""} onChange={(e) => onChange(Number(e.target.value))}>
          {gameweeks.map((gw) => (
            <option key={gw.number} value={gw.number}>
              {optionLabel(gw)}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="gw-step"
        aria-label="Next gameweek"
        disabled={!next}
        onClick={() => onChange(next.number)}
      >
        <span aria-hidden="true">&#8250;</span>
      </button>
    </div>
  );
}
