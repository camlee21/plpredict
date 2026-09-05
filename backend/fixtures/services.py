"""Client for pulling real Premier League fixtures/results from football-data.org.

Free API key: https://www.football-data.org/client/register
The free tier covers the Premier League (competition code "PL") including
the full season's fixture list and live/finished scores, which is all this
project needs.
"""

from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings

STATUS_MAP = {
    "SCHEDULED": "SCHEDULED",
    "TIMED": "SCHEDULED",
    "IN_PLAY": "LIVE",
    "PAUSED": "LIVE",
    "FINISHED": "FINISHED",
    "POSTPONED": "POSTPONED",
    "SUSPENDED": "POSTPONED",
    "CANCELLED": "POSTPONED",
}


class FootballDataError(Exception):
    pass


class FootballDataClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.FOOTBALL_DATA_API_KEY
        if not self.api_key:
            raise FootballDataError(
                "FOOTBALL_DATA_API_KEY is not set. Get a free key at "
                "https://www.football-data.org/client/register and add it to your .env file."
            )
        self.base_url = settings.FOOTBALL_DATA_BASE_URL

    def _get(self, path, params=None):
        response = requests.get(
            f"{self.base_url}{path}",
            headers={"X-Auth-Token": self.api_key},
            params=params or {},
            timeout=15,
        )
        if response.status_code != 200:
            raise FootballDataError(
                f"football-data.org request to {path} failed: "
                f"{response.status_code} {response.text[:200]}"
            )
        return response.json()

    def get_premier_league_matches(self):
        """Returns the raw list of match dicts for the whole PL season."""
        code = settings.PREMIER_LEAGUE_COMPETITION_CODE
        data = self._get(f"/competitions/{code}/matches")
        return data.get("matches", [])


def parse_kickoff(raw_utc_date):
    return datetime.strptime(raw_utc_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt_timezone.utc)


def map_status(raw_status):
    return STATUS_MAP.get(raw_status, "SCHEDULED")
