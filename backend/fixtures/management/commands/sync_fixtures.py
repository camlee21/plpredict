from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.fixtures.models import Fixture, Gameweek, Team
from backend.fixtures.services import FootballDataClient, map_status, parse_kickoff


class Command(BaseCommand):
    help = (
        "Pulls the full Premier League fixture list (and any known results) "
        "from football-data.org and upserts Teams/Gameweeks/Fixtures locally."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        client = FootballDataClient()
        matches = client.get_premier_league_matches()
        if not matches:
            self.stdout.write(self.style.WARNING("No matches returned from the API."))
            return

        touched_gameweeks = set()

        for match in matches:
            matchday = match.get("matchday")
            if not matchday:
                continue

            home_team = self._upsert_team(match["homeTeam"])
            away_team = self._upsert_team(match["awayTeam"])
            gameweek, _ = Gameweek.objects.get_or_create(number=matchday)
            touched_gameweeks.add(gameweek.id)

            full_time = (match.get("score") or {}).get("fullTime") or {}

            Fixture.objects.update_or_create(
                external_id=match["id"],
                defaults={
                    "gameweek": gameweek,
                    "home_team": home_team,
                    "away_team": away_team,
                    "kickoff_time": parse_kickoff(match["utcDate"]),
                    "status": map_status(match.get("status", "SCHEDULED")),
                    "home_score": full_time.get("home"),
                    "away_score": full_time.get("away"),
                },
            )

        for gameweek in Gameweek.objects.filter(id__in=touched_gameweeks):
            gameweek.recompute_schedule(
                settings.PREDICTION_LOCK_BEFORE_KICKOFF,
                settings.GAMEWEEK_FINALIZE_AFTER_LAST_KICKOFF,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(matches)} matches across {len(touched_gameweeks)} gameweeks."
            )
        )

    def _upsert_team(self, raw_team):
        team, _ = Team.objects.update_or_create(
            external_id=raw_team["id"],
            defaults={
                "name": raw_team.get("name", ""),
                "short_name": raw_team.get("shortName", "") or "",
                "tla": raw_team.get("tla", "") or "",
                "crest_url": raw_team.get("crest", "") or "",
            },
        )
        return team
