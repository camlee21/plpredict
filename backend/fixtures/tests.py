from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Fixture, Gameweek, Player, Team, next_predictable_gameweek_number
from .services import map_status, parse_kickoff

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

    def test_map_status_finished(self):
        self.assertEqual(map_status({"finished": True, "started": True}), "FINISHED")

    def test_map_status_live(self):
        self.assertEqual(map_status({"finished": False, "finished_provisional": False, "started": True}), "LIVE")

    def test_map_status_scheduled(self):
        self.assertEqual(map_status({"finished": False, "finished_provisional": False, "started": False}), "SCHEDULED")

    def test_map_status_finished_provisional_counts_as_finished(self):
        # `finished` lags the final whistle until bonus points are locked in;
        # `finished_provisional` flips at full time, which is what a viewer
        # checking the score means by "finished" - not whether bonus points
        # have been confirmed yet.
        self.assertEqual(
            map_status({"finished": False, "finished_provisional": True, "started": True}), "FINISHED"
        )


class TeamFormTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(external_id=1, name="Home FC")
        self.opponent = Team.objects.create(external_id=2, name="Away FC")

    def _finished_fixture(self, external_id, kickoff, home, away, home_score, away_score):
        return Fixture.objects.create(
            external_id=external_id, gameweek=Gameweek.objects.create(number=external_id),
            home_team=home, away_team=away, kickoff_time=kickoff,
            status=Fixture.Status.FINISHED, home_score=home_score, away_score=away_score,
        )

    def test_form_reads_oldest_to_newest_from_the_teams_perspective(self):
        now = timezone.now()
        # Oldest -> newest: win at home, draw away, loss at home.
        self._finished_fixture(1, now - timedelta(days=21), self.team, self.opponent, 2, 0)
        self._finished_fixture(2, now - timedelta(days=14), self.opponent, self.team, 1, 1)
        self._finished_fixture(3, now - timedelta(days=7), self.team, self.opponent, 0, 3)

        self.assertEqual(self.team.recent_form(), ["W", "D", "L"])

    def test_form_only_counts_finished_fixtures(self):
        now = timezone.now()
        self._finished_fixture(1, now - timedelta(days=7), self.team, self.opponent, 1, 0)
        Fixture.objects.create(
            external_id=2, gameweek=Gameweek.objects.create(number=2), home_team=self.team,
            away_team=self.opponent, kickoff_time=now + timedelta(days=7),
        )

        self.assertEqual(self.team.recent_form(), ["W"])

    def test_form_is_capped_at_the_last_five_games(self):
        now = timezone.now()
        for i in range(7):
            self._finished_fixture(i + 1, now - timedelta(days=7 * (7 - i)), self.team, self.opponent, 1, 0)

        self.assertEqual(len(self.team.recent_form()), 5)


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

    def test_lifecycle_reflects_previous_current_and_future(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=7), is_scored=True)
        Gameweek.objects.create(number=2, deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=3, deadline=timezone.now() + timedelta(days=7))

        response = self.client.get(reverse("gameweek-list"))

        by_number = {row["number"]: row for row in response.data}
        self.assertEqual(by_number[1]["lifecycle"], "previous")
        self.assertEqual(by_number[2]["lifecycle"], "current")
        self.assertEqual(by_number[3]["lifecycle"], "future")


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

    def test_fixtures_include_goalscorers_and_team_form(self):
        Fixture.objects.filter(external_id=1).update(
            status=Fixture.Status.FINISHED, home_score=2, away_score=0,
            home_goals=[{"player": "Homer", "count": 2, "own_goal": False}],
            away_goals=[],
        )

        response = self.client.get(reverse("gameweek-detail", args=[7]))

        fixture = response.data["fixtures"][0]
        self.assertEqual(fixture["home_goals"], [{"player": "Homer", "count": 2, "own_goal": False}])
        self.assertEqual(fixture["away_goals"], [])
        self.assertEqual(fixture["home_team"]["form"], ["W"])
        self.assertEqual(fixture["away_team"]["form"], ["L"])

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

    def test_returns_the_earliest_unscored_gameweek(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=7), is_scored=True)
        current = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(hours=2))
        Gameweek.objects.create(number=3, deadline=timezone.now() + timedelta(days=7))

        response = self.client.get(reverse("gameweek-current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], current.number)

    def test_stays_current_even_after_its_own_deadline_has_passed(self):
        # Not yet scored - the gameweek is in progress - so it should stay
        # current rather than jumping ahead just because its own deadline
        # has passed.
        in_progress = Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))

        response = self.client.get(reverse("gameweek-current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], in_progress.number)

    def test_falls_back_to_latest_gameweek_once_the_season_is_fully_scored(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=2), is_scored=True)
        Gameweek.objects.create(number=2, deadline=timezone.now() - timedelta(days=1), is_scored=True)

        response = self.client.get(reverse("gameweek-current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], 2)


class NextPredictableGameweekNumberTests(TestCase):
    def test_none_when_nothing_synced(self):
        self.assertIsNone(next_predictable_gameweek_number())

    def test_returns_the_current_gameweek_while_its_deadline_is_still_open(self):
        current = Gameweek.objects.create(number=1, deadline=timezone.now() + timedelta(hours=2))
        Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))

        self.assertEqual(next_predictable_gameweek_number(), current.number)

    def test_none_once_the_current_gameweeks_deadline_has_passed(self):
        # Gameweek 1 is still current (not yet scored) but no longer
        # predictable - gameweek 2's own deadline being open doesn't matter,
        # only one gameweek is ever predictable at a time.
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))

        self.assertIsNone(next_predictable_gameweek_number())

    def test_none_once_every_gameweek_has_been_scored(self):
        Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=2), is_scored=True)

        self.assertIsNone(next_predictable_gameweek_number())


class HomeGameweekViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def _add_fixture(self, gameweek, kickoff, external_id):
        return Fixture.objects.create(
            external_id=external_id, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=kickoff,
        )

    def test_returns_404_when_nothing_synced(self):
        response = self.client.get(reverse("gameweek-home"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_shows_the_in_progress_gameweek_over_an_upcoming_one(self):
        live = Gameweek.objects.create(
            number=1, finalize_after=timezone.now() + timedelta(hours=1)
        )
        self._add_fixture(live, timezone.now() - timedelta(hours=1), external_id=1)
        upcoming = Gameweek.objects.create(
            number=2, finalize_after=timezone.now() + timedelta(days=8)
        )
        self._add_fixture(upcoming, timezone.now() + timedelta(days=7), external_id=2)

        response = self.client.get(reverse("gameweek-home"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], live.number)
        self.assertEqual(response.data["phase"], "current")

    def test_shows_the_next_upcoming_gameweek_when_none_is_in_progress(self):
        finished = Gameweek.objects.create(
            number=1, finalize_after=timezone.now() - timedelta(days=1)
        )
        self._add_fixture(finished, timezone.now() - timedelta(days=2), external_id=1)
        upcoming = Gameweek.objects.create(
            number=2, finalize_after=timezone.now() + timedelta(days=8)
        )
        self._add_fixture(upcoming, timezone.now() + timedelta(days=7), external_id=2)

        response = self.client.get(reverse("gameweek-home"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], upcoming.number)
        self.assertEqual(response.data["phase"], "upcoming")

    def test_falls_back_to_the_most_recent_gameweek_once_the_season_is_over(self):
        finished = Gameweek.objects.create(
            number=1, finalize_after=timezone.now() - timedelta(days=1)
        )
        self._add_fixture(finished, timezone.now() - timedelta(days=2), external_id=1)

        response = self.client.get(reverse("gameweek-home"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["number"], finished.number)
        self.assertEqual(response.data["phase"], "current")

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("gameweek-home"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


def _bootstrap(teams=None, elements=None):
    return {
        "teams": teams if teams is not None else [
            {"id": 1, "name": "Home FC", "short_name": "HOM"},
            {"id": 2, "name": "Away FC", "short_name": "AWA"},
        ],
        "elements": elements if elements is not None else [
            {"id": 101, "team": 1, "web_name": "Homer"},
            {"id": 102, "team": 2, "web_name": "Awayer"},
        ],
    }


class SyncFixturesCommandTests(TestCase):
    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_fixtures")
    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_bootstrap")
    def test_sync_creates_teams_players_gameweeks_and_fixtures(self, mock_bootstrap, mock_fixtures):
        mock_bootstrap.return_value = _bootstrap()
        mock_fixtures.return_value = [
            {
                "id": 555, "event": 1, "team_h": 1, "team_a": 2,
                "kickoff_time": "2026-08-15T14:00:00Z",
                "started": False, "finished": False,
                "team_h_score": None, "team_a_score": None, "stats": [],
            }
        ]

        from django.core.management import call_command

        call_command("sync_fixtures")

        self.assertEqual(Team.objects.count(), 2)
        self.assertEqual(Player.objects.count(), 2)
        gameweek = Gameweek.objects.get(number=1)
        fixture = Fixture.objects.get(external_id=555)
        self.assertEqual(fixture.gameweek, gameweek)
        self.assertEqual(fixture.status, "SCHEDULED")
        self.assertIsNotNone(gameweek.deadline)
        self.assertEqual(gameweek.deadline, fixture.kickoff_time - timedelta(hours=1))

    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_fixtures")
    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_bootstrap")
    def test_sync_updates_existing_fixture_with_result_and_goalscorers(self, mock_bootstrap, mock_fixtures):
        mock_bootstrap.return_value = _bootstrap()
        raw_fixture = {
            "id": 555, "event": 1, "team_h": 1, "team_a": 2,
            "kickoff_time": "2026-08-15T14:00:00Z",
            "started": False, "finished": False,
            "team_h_score": None, "team_a_score": None, "stats": [],
        }
        mock_fixtures.return_value = [raw_fixture]

        from django.core.management import call_command

        call_command("sync_fixtures")

        raw_fixture["started"] = True
        raw_fixture["finished"] = True
        raw_fixture["team_h_score"] = 2
        raw_fixture["team_a_score"] = 1
        raw_fixture["stats"] = [
            {"identifier": "goals_scored", "h": [{"value": 2, "element": 101}], "a": [{"value": 1, "element": 102}]},
        ]
        call_command("sync_fixtures")

        fixture = Fixture.objects.get(external_id=555)
        self.assertEqual(fixture.status, "FINISHED")
        self.assertEqual(fixture.home_score, 2)
        self.assertEqual(fixture.away_score, 1)
        self.assertEqual(fixture.home_goals, [{"player": "Homer", "count": 2, "own_goal": False}])
        self.assertEqual(fixture.away_goals, [{"player": "Awayer", "count": 1, "own_goal": False}])
        self.assertEqual(Fixture.objects.count(), 1)

    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_fixtures")
    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_bootstrap")
    def test_sync_attributes_own_goals_to_the_opposing_team(self, mock_bootstrap, mock_fixtures):
        mock_bootstrap.return_value = _bootstrap()
        mock_fixtures.return_value = [
            {
                "id": 555, "event": 1, "team_h": 1, "team_a": 2,
                "kickoff_time": "2026-08-15T14:00:00Z",
                "started": True, "finished": True,
                "team_h_score": 0, "team_a_score": 1,
                "stats": [
                    {"identifier": "own_goals", "h": [{"value": 1, "element": 101}], "a": []},
                ],
            }
        ]

        from django.core.management import call_command

        call_command("sync_fixtures")

        fixture = Fixture.objects.get(external_id=555)
        self.assertEqual(fixture.home_goals, [])
        self.assertEqual(fixture.away_goals, [{"player": "Homer", "count": 1, "own_goal": True}])

    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_fixtures")
    @patch("backend.fixtures.management.commands.sync_fixtures.FPLClient.get_bootstrap")
    def test_sync_skips_fixtures_without_a_confirmed_kickoff(self, mock_bootstrap, mock_fixtures):
        mock_bootstrap.return_value = _bootstrap()
        mock_fixtures.return_value = [
            {"id": 555, "event": None, "team_h": 1, "team_a": 2, "kickoff_time": None, "stats": []},
        ]

        from django.core.management import call_command

        call_command("sync_fixtures")

        self.assertEqual(Fixture.objects.count(), 0)
