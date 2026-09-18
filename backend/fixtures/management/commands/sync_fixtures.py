from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.fixtures.models import Fixture, Gameweek, Player, Team
from backend.fixtures.services import FPLClient, map_status, parse_kickoff

BATCH_SIZE = 200


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
        synced, touched_gameweeks = self._sync_fixtures(fixtures, teams_by_external_id, players_by_external_id)

        for gameweek in Gameweek.objects.filter(id__in=touched_gameweeks):
            gameweek.recompute_schedule(
                settings.PREDICTION_LOCK_BEFORE_KICKOFF,
                settings.GAMEWEEK_FINALIZE_AFTER_LAST_KICKOFF,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Synced {synced} fixtures across {len(touched_gameweeks)} gameweeks.")
        )

    def _sync_teams(self, raw_teams):
        # Batched (bulk_create/bulk_update) rather than one update_or_create
        # per row - each of those is its own DB round-trip, and hundreds of
        # them in a single request is slow enough to blow past Gunicorn's
        # worker timeout on a remote (Neon) database.
        external_ids = [raw["id"] for raw in raw_teams]
        existing = {t.external_id: t for t in Team.objects.filter(external_id__in=external_ids)}

        to_create, to_update = [], []
        for raw in raw_teams:
            code = raw.get("code")
            fields = {
                "name": raw.get("name", ""),
                "short_name": raw.get("short_name", "") or "",
                "tla": (raw.get("short_name") or "")[:5],
                "crest_url": (
                    f"https://resources.premierleague.com/premierleague/badges/70/t{code}.png"
                    if code
                    else ""
                ),
            }
            team = existing.get(raw["id"])
            if team is None:
                to_create.append(Team(external_id=raw["id"], **fields))
            else:
                for field, value in fields.items():
                    setattr(team, field, value)
                to_update.append(team)

        if to_create:
            Team.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        if to_update:
            Team.objects.bulk_update(
                to_update, fields=["name", "short_name", "tla", "crest_url"], batch_size=BATCH_SIZE
            )

        # Re-fetch so newly-created teams' ids are included regardless of
        # whether the DB backend returns them from bulk_create.
        return {t.external_id: t for t in Team.objects.filter(external_id__in=external_ids)}

    def _sync_players(self, raw_elements, teams_by_external_id):
        external_ids = [raw["id"] for raw in raw_elements]
        existing = {p.external_id: p for p in Player.objects.filter(external_id__in=external_ids)}

        to_create, to_update = [], []
        for raw in raw_elements:
            team = teams_by_external_id.get(raw.get("team"))
            if team is None:
                continue
            player = existing.get(raw["id"])
            if player is None:
                to_create.append(Player(external_id=raw["id"], team=team, web_name=raw.get("web_name", "")))
            else:
                player.team = team
                player.web_name = raw.get("web_name", "")
                to_update.append(player)

        if to_create:
            Player.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        if to_update:
            Player.objects.bulk_update(to_update, fields=["team", "web_name"], batch_size=BATCH_SIZE)

    def _sync_fixtures(self, raw_fixtures, teams_by_external_id, players_by_external_id):
        valid = []
        for raw in raw_fixtures:
            gameweek_number = raw.get("event")
            kickoff_raw = raw.get("kickoff_time")
            if not gameweek_number or not kickoff_raw:
                continue  # Not yet scheduled (e.g. postponed, TBC).

            home_team = teams_by_external_id.get(raw["team_h"])
            away_team = teams_by_external_id.get(raw["team_a"])
            if home_team is None or away_team is None:
                continue

            valid.append((raw, gameweek_number, home_team, away_team))

        gameweeks_by_number = self._ensure_gameweeks(number for _, number, _, _ in valid)

        external_ids = [raw["id"] for raw, _, _, _ in valid]
        existing_fixtures = {f.external_id: f for f in Fixture.objects.filter(external_id__in=external_ids)}

        to_create, to_update = [], []
        touched_gameweeks = set()
        for raw, gameweek_number, home_team, away_team in valid:
            gameweek = gameweeks_by_number[gameweek_number]
            touched_gameweeks.add(gameweek.id)

            home_goals, away_goals = self._extract_goalscorers(raw.get("stats", []), players_by_external_id)
            fields = {
                "gameweek": gameweek,
                "home_team": home_team,
                "away_team": away_team,
                "kickoff_time": parse_kickoff(raw["kickoff_time"]),
                "status": map_status(raw),
                "home_score": raw.get("team_h_score"),
                "away_score": raw.get("team_a_score"),
                "home_goals": home_goals,
                "away_goals": away_goals,
            }

            fixture = existing_fixtures.get(raw["id"])
            if fixture is None:
                to_create.append(Fixture(external_id=raw["id"], **fields))
            else:
                for field, value in fields.items():
                    setattr(fixture, field, value)
                to_update.append(fixture)

        if to_create:
            Fixture.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        if to_update:
            Fixture.objects.bulk_update(
                to_update,
                fields=[
                    "gameweek", "home_team", "away_team", "kickoff_time", "status",
                    "home_score", "away_score", "home_goals", "away_goals",
                ],
                batch_size=BATCH_SIZE,
            )

        return len(valid), touched_gameweeks

    def _ensure_gameweeks(self, numbers):
        numbers = set(numbers)
        gameweeks_by_number = {gw.number: gw for gw in Gameweek.objects.filter(number__in=numbers)}
        missing = numbers - gameweeks_by_number.keys()
        if missing:
            Gameweek.objects.bulk_create([Gameweek(number=number) for number in missing], batch_size=BATCH_SIZE)
            gameweeks_by_number = {gw.number: gw for gw in Gameweek.objects.filter(number__in=numbers)}
        return gameweeks_by_number

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
