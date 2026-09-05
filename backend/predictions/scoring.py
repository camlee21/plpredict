"""Scoring rules for a single prediction against a final score.

- 1 point for the correct result (home win / away win / draw)
- 3 points for the correct scoreline (which implies the correct result)
- 4 points for the correct scoreline when the match had 5+ total goals,
  rewarding riskier, higher-scoring predictions.
"""


def _result(home, away):
    if home > away:
        return "H"
    if home < away:
        return "A"
    return "D"


def calculate_points(predicted_home, predicted_away, actual_home, actual_away):
    if predicted_home == actual_home and predicted_away == actual_away:
        total_goals = actual_home + actual_away
        return 4 if total_goals >= 5 else 3

    if _result(predicted_home, predicted_away) == _result(actual_home, actual_away):
        return 1

    return 0
