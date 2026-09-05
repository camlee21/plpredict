from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Fixture, Gameweek, Team
from .services import FootballDataError, FootballDataClient, map_status, parse_kickoff

User = get_user_model()


class GameweekModelTests(TestCase):
    def test_recompute_schedule_sets_deadline_and_finalize_after(self):
        home = Team.objects.create(external_id=1, name="Home FC")
        away = Team.objects.create(external_id=2, name="Away FC")
        gameweek = Gameweek.objects.create(number=1)

        early_kickoff = timezone.now() + timedelta(days=1)
        late_kickoff = early_kickoff + timedelta(hours=5)
        Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=home, away_team=away, kickoff_time=early_kickoff
        )
        Fixture.objects.create(
            external_id=2, gameweek=gameweek, home_team=home, away_team=away, kickoff_time=late_kickoff
        )

        gameweek.recompute_schedule(timedelta(hours=1), timedelta(hours=2, minutes=30))
        gameweek.refresh_from_db()

        self.assertEqual(gameweek.deadline, early_kickoff - timedelta(hours=1))
        self.assertEqual(gameweek.finalize_after, late_kickoff + timedelta(hours=2, minutes=30))

    def test_recompute_schedule_noop_without_fixtures(self):
        gameweek = Gameweek.objects.create(number=1)
        gameweek.recompute_schedule(timedelta(hours=1), timedelta(hours=2))
        gameweek.refresh_from_db()
        self.assertIsNone(gameweek.deadline)


class ServiceHelperTests(TestCase):
    def test_parse_kickoff(self):
        dt = parse_kickoff("2026-03-05T14:00:00Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 14)
        self.assertIsNotNone(dt.tzinfo)

    def test_map_status_known_and_unknown(self):
        self.assertEqual(map_status("IN_PLAY"), "LIVE")
        self.assertEqual(map_status("FINISHED"), "FINISHED")
        self.assertEqual(map_status("SOMETHING_NEW"), "SCHEDULED")

    @override_settings(FOOTBALL_DATA_API_KEY="")
    def test_client_requires_api_key(self):
        with self.assertRaises(FootballDataError):
            FootballDataClient()


class GameweekListViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("gameweek-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_gameweeks_with_lock_status(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(hours=1))

        response = self.client.get(reverse("gameweek-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_number = {row["number"]: row for row in response.data}
        self.assertTrue(by_number[1]["is_locked"])
        self.assertFalse(by_number[2]["is_locked"])

    def test_gameweek_with_no_deadline_is_locked(self):
        Gameweek.objects.create(number=1)
        response = self.client.get(reverse("gameweek-list"))
        self.assertTrue(response.data[0]["is_locked"])


class GameweekDetailViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")
        self.gameweek = Gameweek.objects.create(number=7)
        Fixture.objects.create(
            external_id=1, gameweek=self.gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now(),
        )

    def test_returns_nested_fixtures(self):
        response = self.client.get(reverse("gameweek-detail", args=[7]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["fixtures"]), 1)
        self.assertEqual(response.data["fixtures"][0]["home_team"]["name"], "Home FC")

    def test_unknown_gameweek_returns_404(self):
        response = self.client.get(reverse("gameweek-detail", args=[999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CurrentGameweekViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)

    def test_returns_404_when_nothing_synced(self):
        response = self.client.get(reverse("gameweek-current"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_next_upcoming_gameweek(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=1))
        soon = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(hours=2))
        Gameweek.objects.create(number=3, deadline=timezone.now() + timedelta(days=7))

        response = self.client.get(reverse("gameweek-current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], soon.number)

    def test_falls_back_to_latest_gameweek_when_all_locked(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=2))
        Gameweek.objects.create(number=2, deadline=timezone.now() - timedelta(days=1))

        response = self.client.get(reverse("gameweek-current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], 2)


class SyncFixturesCommandTests(TestCase):
    @override_settings(FOOTBALL_DATA_API_KEY="test-key")
    @patch("backend.fixtures.management.commands.sync_fixtures.FootballDataClient.get_premier_league_matches")
    def test_sync_creates_teams_gameweeks_and_fixtures(self, mock_matches):
        mock_matches.return_value = [
            {
                "id": 555,
                "matchday": 1,
                "utcDate": "2026-08-15T14:00:00Z",
                "status": "SCHEDULED",
                "homeTeam": {"id": 1, "name": "Home FC", "shortName": "Home", "tla": "HOM", "crest": ""},
                "awayTeam": {"id": 2, "name": "Away FC", "shortName": "Away", "tla": "AWA", "crest": ""},
                "score": {"fullTime": {"home": None, "away": None}},
            }
        ]

        from django.core.management import call_command

        call_command("sync_fixtures")

        self.assertEqual(Team.objects.count(), 2)
        gameweek = Gameweek.objects.get(number=1)
        fixture = Fixture.objects.get(external_id=555)
        self.assertEqual(fixture.gameweek, gameweek)
        self.assertEqual(fixture.status, "SCHEDULED")
        self.assertIsNotNone(gameweek.deadline)
        self.assertEqual(gameweek.deadline, fixture.kickoff_time - timedelta(hours=1))

    @override_settings(FOOTBALL_DATA_API_KEY="test-key")
    @patch("backend.fixtures.management.commands.sync_fixtures.FootballDataClient.get_premier_league_matches")
    def test_sync_updates_existing_fixture_with_result(self, mock_matches):
        from django.core.management import call_command

        mock_matches.return_value = [
            {
                "id": 555,
                "matchday": 1,
                "utcDate": "2026-08-15T14:00:00Z",
                "status": "SCHEDULED",
                "homeTeam": {"id": 1, "name": "Home FC"},
                "awayTeam": {"id": 2, "name": "Away FC"},
                "score": {"fullTime": {"home": None, "away": None}},
            }
        ]
        call_command("sync_fixtures")

        mock_matches.return_value[0]["status"] = "FINISHED"
        mock_matches.return_value[0]["score"] = {"fullTime": {"home": 2, "away": 1}}
        call_command("sync_fixtures")

        fixture = Fixture.objects.get(external_id=555)
        self.assertEqual(fixture.status, "FINISHED")
        self.assertEqual(fixture.home_score, 2)
        self.assertEqual(fixture.away_score, 1)
        self.assertEqual(Fixture.objects.count(), 1)
