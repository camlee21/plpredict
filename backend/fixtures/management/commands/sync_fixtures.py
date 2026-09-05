from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.fixtures.models import Fixture, Gameweek, Player, Team
from backend.fixtures.services import FPLClient, map_status, parse_kickoff


class Command(BaseCommand):
    help = (
        "Pulls the current season's teams, players and fixtures (including "
        "results and goalscorers) from the Fantasy Premier League API and "
        "upserts them locally."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        client = FPLClient()
        bootstrap = client.get_bootstrap()

        teams_by_external_id = self._sync_teams(bootstrap.get("teams", []))
        self._sync_players(bootstrap.get("elements", []), teams_by_external_id)
        players_by_external_id = dict(Player.objects.values_list("external_id", "web_name"))

        fixtures = client.get_fixtures()
        touched_gameweeks = set()
        synced = 0

        for raw in fixtures:
            gameweek_number = raw.get("event")
            kickoff_raw = raw.get("kickoff_time")
            if not gameweek_number or not kickoff_raw:
                continue  # Not yet scheduled (e.g. postponed, TBC).

            home_team = teams_by_external_id.get(raw["team_h"])
            away_team = teams_by_external_id.get(raw["team_a"])
            if home_team is None or away_team is None:
                continue

            gameweek, _ = Gameweek.objects.get_or_create(number=gameweek_number)
            touched_gameweeks.add(gameweek.id)

            home_goals, away_goals = self._extract_goalscorers(raw.get("stats", []), players_by_external_id)

            Fixture.objects.update_or_create(
                external_id=raw["id"],
                defaults={
                    "gameweek": gameweek,
                    "home_team": home_team,
                    "away_team": away_team,
                    "kickoff_time": parse_kickoff(kickoff_raw),
                    "status": map_status(raw),
                    "home_score": raw.get("team_h_score"),
                    "away_score": raw.get("team_a_score"),
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                },
            )
            synced += 1

        for gameweek in Gameweek.objects.filter(id__in=touched_gameweeks):
            gameweek.recompute_schedule(
                settings.PREDICTION_LOCK_BEFORE_KICKOFF,
                settings.GAMEWEEK_FINALIZE_AFTER_LAST_KICKOFF,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Synced {synced} fixtures across {len(touched_gameweeks)} gameweeks.")
        )

    def _sync_teams(self, raw_teams):
        by_external_id = {}
        for raw in raw_teams:
            code = raw.get("code")
            team, _ = Team.objects.update_or_create(
                external_id=raw["id"],
                defaults={
                    "name": raw.get("name", ""),
                    "short_name": raw.get("short_name", "") or "",
                    "tla": (raw.get("short_name") or "")[:5],
                    "crest_url": (
                        f"https://resources.premierleague.com/premierleague/badges/70/t{code}.png"
                        if code
                        else ""
                    ),
                },
            )
            by_external_id[raw["id"]] = team
        return by_external_id

    def _sync_players(self, raw_elements, teams_by_external_id):
        for raw in raw_elements:
            team = teams_by_external_id.get(raw.get("team"))
            if team is None:
                continue
            Player.objects.update_or_create(
                external_id=raw["id"],
                defaults={"team": team, "web_name": raw.get("web_name", "")},
            )

    def _extract_goalscorers(self, stats, players_by_external_id):
        home_goals, away_goals = [], []
        for stat in stats:
            identifier = stat.get("identifier")
            if identifier == "goals_scored":
                self._collect(stat.get("h", []), players_by_external_id, home_goals, own_goal=False)
                self._collect(stat.get("a", []), players_by_external_id, away_goals, own_goal=False)
            elif identifier == "own_goals":
                # An own goal by a home player counts for the away side, and vice versa.
                self._collect(stat.get("h", []), players_by_external_id, away_goals, own_goal=True)
                self._collect(stat.get("a", []), players_by_external_id, home_goals, own_goal=True)
        return home_goals, away_goals

    def _collect(self, entries, players_by_external_id, target, own_goal):
        for entry in entries:
            name = players_by_external_id.get(entry.get("element"), "Unknown")
            target.append({"player": name, "count": entry.get("value", 1), "own_goal": own_goal})
