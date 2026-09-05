"""Client for pulling real Premier League data from the Fantasy Premier
League (FPL) API.

This is the same public API that powers the official FPL game. It's free,
requires no API key, and covers the current season's teams, players,
fixtures, scores and per-fixture goalscorer stats - everything this project
needs.
"""

from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings


class FPLError(Exception):
    pass


class FPLClient:
    def __init__(self, base_url=None):
        self.base_url = base_url or settings.FPL_BASE_URL

    def _get(self, path):
        response = requests.get(f"{self.base_url}{path}", timeout=15)
        if response.status_code != 200:
            raise FPLError(f"FPL API request to {path} failed: {response.status_code} {response.text[:200]}")
        return response.json()

    def get_bootstrap(self):
        """Teams and players for the current season."""
        return self._get("/bootstrap-static/")

    def get_fixtures(self):
        """The full season's fixtures, including results and stats for
        finished matches."""
        return self._get("/fixtures/")


def parse_kickoff(raw_utc_date):
    return datetime.strptime(raw_utc_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt_timezone.utc)


def map_status(raw_fixture):
    # `finished` only flips once bonus points are confirmed, which can lag
    # the final whistle by an hour or more. `finished_provisional` flips as
    # soon as full time is reached, which is what "Finished" should mean to
    # a user checking the score - not whether bonus points are locked in yet.
    if raw_fixture.get("finished") or raw_fixture.get("finished_provisional"):
        return "FINISHED"
    if raw_fixture.get("started"):
        return "LIVE"
    return "SCHEDULED"
