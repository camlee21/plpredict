from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from backend.fixtures.models import Fixture, Gameweek, Team
from backend.predictions.models import Prediction

from .models import League, LeagueMembership

User = get_user_model()


class LeagueCreationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)

    def test_create_league_generates_six_char_uppercase_code(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        code = response.data["code"]
        self.assertEqual(len(code), 6)
        self.assertEqual(code, code.upper())
        self.assertTrue(code.isalnum())

    def test_create_league_generates_eight_char_uppercase_public_id(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        public_id = response.data["public_id"]
        self.assertEqual(len(public_id), 8)
        self.assertEqual(public_id, public_id.upper())
        self.assertTrue(public_id.isalnum())

    def test_public_id_and_code_are_different_and_do_not_expose_numeric_pk(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})
        self.assertNotEqual(response.data["public_id"], response.data["code"])
        self.assertNotIn("id", response.data)

    def test_league_defaults_to_public_with_eight_max_members(self):
        # JSON, not the default multipart test-client format: a form-encoded
        # POST omitting a BooleanField is treated by DRF as an unchecked
        # HTML checkbox (explicit False), which would mask the real model
        # default here. Our frontend always sends JSON, as a real client
        # that just omits the field (rather than submitting an HTML form)
        # would.
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"}, format="json")

        self.assertTrue(response.data["is_public"])
        self.assertEqual(response.data["max_members"], 8)

    def test_can_create_private_league_with_custom_max_members(self):
        response = self.client.post(
            reverse("league-list-create"),
            {"name": "Closed League", "is_public": False, "max_members": 32},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["is_public"])
        self.assertEqual(response.data["max_members"], 32)

    def test_rejects_max_members_outside_allowed_choices(self):
        response = self.client.post(
            reverse("league-list-create"), {"name": "Office League", "max_members": 10}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accepts_every_allowed_max_members_choice(self):
        for choice in (4, 8, 16, 32, 64, 128):
            response = self.client.post(
                reverse("league-list-create"), {"name": f"League {choice}", "max_members": choice}
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, choice)
            self.assertEqual(response.data["max_members"], choice)

    def test_creator_is_automatically_a_member(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})
        league = League.objects.get(public_id=response.data["public_id"])

        self.assertTrue(LeagueMembership.objects.filter(league=league, user=self.user).exists())
        self.assertEqual(response.data["member_count"], 1)
        self.assertEqual(response.data["owner_username"], "alice")

    def test_league_codes_are_unique(self):
        r1 = self.client.post(reverse("league-list-create"), {"name": "League One"})
        r2 = self.client.post(reverse("league-list-create"), {"name": "League Two"})
        self.assertNotEqual(r1.data["code"], r2.data["code"])
        self.assertNotEqual(r1.data["public_id"], r2.data["public_id"])

    def test_list_only_returns_my_leagues(self):
        other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        League.objects.create(name="Not mine", owner=other_user)

        self.client.post(reverse("league-list-create"), {"name": "Mine"})
        response = self.client.get(reverse("league-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Mine")

    def test_list_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("league-list-create"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MaxLeaguesPerUserTests(APITestCase):
    """A user can be a member of at most 10 leagues at once, whether they get
    there by creating a league or by joining one (by code or publicly)."""

    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.joiner = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        for i in range(10):
            league = League.objects.create(name=f"League {i}", owner=self.owner, is_public=True, max_members=20)
            LeagueMembership.objects.create(league=league, user=self.joiner)
        self.client.force_authenticate(user=self.joiner)

    def test_cannot_create_an_11th_league(self):
        response = self.client.post(reverse("league-list-create"), {"name": "One Too Many"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(League.objects.filter(name="One Too Many").exists())

    def test_cannot_join_an_11th_league_by_code(self):
        extra = League.objects.create(name="Extra League", owner=self.owner, max_members=20)
        LeagueMembership.objects.create(league=extra, user=self.owner)

        response = self.client.post(reverse("league-join"), {"code": extra.code})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(LeagueMembership.objects.filter(league=extra, user=self.joiner).exists())

    def test_cannot_join_an_11th_public_league(self):
        extra = League.objects.create(name="Extra Public League", owner=self.owner, is_public=True, max_members=20)
        LeagueMembership.objects.create(league=extra, user=self.owner)

        response = self.client.post(reverse("league-join-public", args=[extra.public_id]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(LeagueMembership.objects.filter(league=extra, user=self.joiner).exists())


class JoinByCodeTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.joiner = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.league = League.objects.create(name="Office League", owner=self.owner, max_members=8)
        LeagueMembership.objects.create(league=self.league, user=self.owner)
        self.client.force_authenticate(user=self.joiner)

    def test_join_with_valid_code(self):
        response = self.client.post(reverse("league-join"), {"code": self.league.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(LeagueMembership.objects.filter(league=self.league, user=self.joiner).exists())

    def test_join_is_case_insensitive(self):
        response = self.client.post(reverse("league-join"), {"code": self.league.code.lower()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_joining_twice_does_not_duplicate_membership(self):
        self.client.post(reverse("league-join"), {"code": self.league.code})
        self.client.post(reverse("league-join"), {"code": self.league.code})

        self.assertEqual(LeagueMembership.objects.filter(league=self.league, user=self.joiner).count(), 1)

    def test_join_with_unknown_code_returns_404(self):
        response = self.client.post(reverse("league-join"), {"code": "ZZZZZZ"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_join_rejects_wrong_length_code(self):
        response = self.client.post(reverse("league-join"), {"code": "ABC"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_join_by_code_works_for_a_public_league_too(self):
        public_league = League.objects.create(name="Open League", owner=self.owner, is_public=True)
        LeagueMembership.objects.create(league=public_league, user=self.owner)

        response = self.client.post(reverse("league-join"), {"code": public_league.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(LeagueMembership.objects.filter(league=public_league, user=self.joiner).exists())

    def test_cannot_join_full_league_by_code(self):
        full_league = League.objects.create(name="Tiny League", owner=self.owner, max_members=1)
        LeagueMembership.objects.create(league=full_league, user=self.owner)

        response = self.client.post(reverse("league-join"), {"code": full_league.code})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(LeagueMembership.objects.filter(league=full_league, user=self.joiner).exists())


class JoinPublicLeagueTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.joiner = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.public_league = League.objects.create(name="Open League", owner=self.owner, is_public=True, max_members=8)
        LeagueMembership.objects.create(league=self.public_league, user=self.owner)
        self.private_league = League.objects.create(name="Closed League", owner=self.owner, is_public=False)
        LeagueMembership.objects.create(league=self.private_league, user=self.owner)
        self.client.force_authenticate(user=self.joiner)

    def test_can_join_public_league_without_a_code(self):
        response = self.client.post(reverse("league-join-public", args=[self.public_league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(LeagueMembership.objects.filter(league=self.public_league, user=self.joiner).exists())

    def test_cannot_join_private_league_via_public_join_endpoint(self):
        response = self.client.post(reverse("league-join-public", args=[self.private_league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(LeagueMembership.objects.filter(league=self.private_league, user=self.joiner).exists())

    def test_joining_public_league_twice_does_not_duplicate_membership(self):
        self.client.post(reverse("league-join-public", args=[self.public_league.public_id]))
        self.client.post(reverse("league-join-public", args=[self.public_league.public_id]))

        self.assertEqual(
            LeagueMembership.objects.filter(league=self.public_league, user=self.joiner).count(), 1
        )

    def test_unknown_public_id_returns_404(self):
        response = self.client.post(reverse("league-join-public", args=["ZZZZZZZZ"]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_join_full_public_league(self):
        full_league = League.objects.create(name="Full League", owner=self.owner, is_public=True, max_members=1)
        LeagueMembership.objects.create(league=full_league, user=self.owner)

        response = self.client.post(reverse("league-join-public", args=[full_league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(LeagueMembership.objects.filter(league=full_league, user=self.joiner).exists())

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(reverse("league-join-public", args=[self.public_league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LeaveLeagueTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.member = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.outsider = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")
        self.league = League.objects.create(name="Office League", owner=self.owner, is_public=True, max_members=8)
        LeagueMembership.objects.create(league=self.league, user=self.owner)
        LeagueMembership.objects.create(league=self.league, user=self.member)

    def test_a_member_can_leave(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(reverse("league-leave", args=[self.league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LeagueMembership.objects.filter(league=self.league, user=self.member).exists())

    def test_the_owner_cannot_leave_their_own_league(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(reverse("league-leave", args=[self.league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(LeagueMembership.objects.filter(league=self.league, user=self.owner).exists())

    def test_a_non_member_cannot_leave(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(reverse("league-leave", args=[self.league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_public_id_returns_404(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(reverse("league-leave", args=["ZZZZZZZZ"]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        response = self.client.post(reverse("league-leave", args=[self.league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_leaving_frees_a_spot_for_a_previously_full_public_league_to_reappear_in_search(self):
        full_league = League.objects.create(name="Snug League", owner=self.owner, is_public=True, max_members=2)
        LeagueMembership.objects.create(league=full_league, user=self.owner)
        LeagueMembership.objects.create(league=full_league, user=self.member)

        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(reverse("league-browse"))
        self.assertNotIn("Snug League", [row["name"] for row in response.data])

        self.client.force_authenticate(user=self.member)
        self.client.post(reverse("league-leave", args=[full_league.public_id]))

        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(reverse("league-browse"))
        self.assertIn("Snug League", [row["name"] for row in response.data])


class PublicLeagueBrowseTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.viewer = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.public_league = League.objects.create(name="Open League", owner=self.owner, is_public=True, max_members=2)
        LeagueMembership.objects.create(league=self.public_league, user=self.owner)
        self.private_league = League.objects.create(name="Closed League", owner=self.owner, is_public=False)
        LeagueMembership.objects.create(league=self.private_league, user=self.owner)
        self.client.force_authenticate(user=self.viewer)

    def test_only_lists_public_leagues(self):
        response = self.client.get(reverse("league-browse"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data]
        self.assertIn("Open League", names)
        self.assertNotIn("Closed League", names)

    def test_browse_listing_never_exposes_the_join_code(self):
        response = self.client.get(reverse("league-browse"))
        for row in response.data:
            self.assertNotIn("code", row)

    def test_browse_listing_reports_membership_and_capacity(self):
        response = self.client.get(reverse("league-browse"))
        row = next(r for r in response.data if r["public_id"] == self.public_league.public_id)

        self.assertFalse(row["is_member"])
        self.assertFalse(row["is_full"])
        self.assertEqual(row["member_count"], 1)
        self.assertEqual(row["max_members"], 2)

    def test_full_leagues_are_excluded_from_the_listing_entirely(self):
        LeagueMembership.objects.create(league=self.public_league, user=self.viewer)
        other_user = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")
        self.client.force_authenticate(user=other_user)

        response = self.client.get(reverse("league-browse"))

        ids = [row["public_id"] for row in response.data]
        self.assertNotIn(self.public_league.public_id, ids)

    def test_browse_listing_flags_leagues_i_have_already_joined(self):
        roomier_league = League.objects.create(
            name="Roomier League", owner=self.owner, is_public=True, max_members=8
        )
        LeagueMembership.objects.create(league=roomier_league, user=self.owner)
        LeagueMembership.objects.create(league=roomier_league, user=self.viewer)

        response = self.client.get(reverse("league-browse"))
        row = next(r for r in response.data if r["public_id"] == roomier_league.public_id)

        self.assertTrue(row["is_member"])

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("league-browse"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LeagueDetailLookupTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.league = League.objects.create(name="Office League", owner=self.owner)
        LeagueMembership.objects.create(league=self.league, user=self.owner)
        self.client.force_authenticate(user=self.owner)

    def test_detail_is_looked_up_by_public_id_not_numeric_pk(self):
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["public_id"], self.league.public_id)

    def test_numeric_pk_is_not_a_valid_lookup(self):
        response = self.client.get(reverse("league-detail", args=[str(self.league.pk)]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_can_see_the_join_code_in_league_detail(self):
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertEqual(response.data["code"], self.league.code)

    def test_detail_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LeagueStandingsTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.outsider = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")

        self.league = League.objects.create(name="Office League", owner=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.bob)

        home = Team.objects.create(external_id=1, name="Home FC")
        away = Team.objects.create(external_id=2, name="Away FC")
        gameweek = Gameweek.objects.create(number=1, is_scored=True)
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=home, away_team=away,
            kickoff_time=timezone.now(), status=Fixture.Status.FINISHED, home_score=2, away_score=1,
        )
        Prediction.objects.create(user=self.alice, fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=3)
        Prediction.objects.create(user=self.bob, fixture=fixture, predicted_home_score=1, predicted_away_score=1, points=0)

    def test_standings_are_sorted_by_points_descending(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        standings = response.data["standings"]
        self.assertEqual(standings[0]["username"], "alice")
        self.assertEqual(standings[0]["total_points"], 3)
        self.assertEqual(standings[1]["username"], "bob")
        self.assertEqual(standings[1]["total_points"], 0)

    def test_is_owner_flag(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertFalse(response.data["is_owner"])

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertTrue(response.data["is_owner"])

    def test_non_member_cannot_view_league(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LeagueCurrentGameweekPointsTests(APITestCase):
    """A gameweek's points only join total_points once it's officially
    scored; until then they show up as a separate, live current_gameweek_points
    figure computed from whichever of its fixtures have already finished."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.league = League.objects.create(name="Office League", owner=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.bob)
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def test_live_points_from_a_finished_fixture_in_the_current_unscored_gameweek(self):
        gameweek = Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(hours=1))
        finished = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=2),
            status=Fixture.Status.FINISHED, home_score=2, away_score=1,
        )
        unfinished = Fixture.objects.create(
            external_id=2, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(hours=1),
        )
        Prediction.objects.create(user=self.alice, fixture=finished, predicted_home_score=2, predicted_away_score=1)
        Prediction.objects.create(user=self.alice, fixture=unfinished, predicted_home_score=1, predicted_away_score=0)
        Prediction.objects.create(user=self.bob, fixture=finished, predicted_home_score=0, predicted_away_score=0)

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))

        self.assertEqual(response.data["current_gameweek"], 1)
        by_username = {row["username"]: row for row in response.data["standings"]}
        self.assertEqual(by_username["alice"]["current_gameweek_points"], 3)
        self.assertEqual(by_username["alice"]["total_points"], 0)
        self.assertEqual(by_username["bob"]["current_gameweek_points"], 0)

    def test_resets_to_zero_and_folds_into_total_once_the_gameweek_is_scored(self):
        gameweek = Gameweek.objects.create(number=1, is_scored=True)
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(days=1),
            status=Fixture.Status.FINISHED, home_score=2, away_score=1,
        )
        Prediction.objects.create(
            user=self.alice, fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=3
        )
        next_gameweek = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))
        Fixture.objects.create(
            external_id=2, gameweek=next_gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(days=7),
        )

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))

        self.assertEqual(response.data["current_gameweek"], 2)
        alice = next(row for row in response.data["standings"] if row["username"] == "alice")
        self.assertEqual(alice["total_points"], 3)
        self.assertEqual(alice["current_gameweek_points"], 0)


class LeagueStandingsTiedRankingTests(APITestCase):
    """u1=20, u2=18, u3=17, u4=17, u5=15 -> 1st, 2nd, =3rd, =3rd, 5th."""

    def setUp(self):
        self.users = {
            name: User.objects.create_user(username=name, email=f"{name}@example.com", password="pw12345678")
            for name in ("u1", "u2", "u3", "u4", "u5")
        }
        self.league = League.objects.create(name="Ranked League", owner=self.users["u1"])
        for user in self.users.values():
            LeagueMembership.objects.create(league=self.league, user=user)

        home = Team.objects.create(external_id=1, name="Home FC")
        away = Team.objects.create(external_id=2, name="Away FC")
        gameweek = Gameweek.objects.create(number=1, is_scored=True)
        points_by_user = {"u1": 20, "u2": 18, "u3": 17, "u4": 17, "u5": 15}
        for index, (name, points) in enumerate(points_by_user.items()):
            fixture = Fixture.objects.create(
                external_id=index + 1, gameweek=gameweek, home_team=home, away_team=away,
                kickoff_time=timezone.now(), status=Fixture.Status.FINISHED, home_score=2, away_score=1,
            )
            Prediction.objects.create(
                user=self.users[name], fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=points
            )

    def test_tied_scores_share_a_rank_and_skip_the_next(self):
        self.client.force_authenticate(user=self.users["u1"])
        response = self.client.get(reverse("league-detail", args=[self.league.public_id]))

        by_username = {row["username"]: row for row in response.data["standings"]}
        self.assertEqual(by_username["u1"]["rank_display"], "1st")
        self.assertEqual(by_username["u2"]["rank_display"], "2nd")
        self.assertEqual(by_username["u3"]["rank_display"], "=3rd")
        self.assertEqual(by_username["u4"]["rank_display"], "=3rd")
        self.assertEqual(by_username["u5"]["rank_display"], "5th")


class LeagueHomeSummaryTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")

        self.league = League.objects.create(name="Office League", owner=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.alice)
        LeagueMembership.objects.create(league=self.league, user=self.bob)

        home = Team.objects.create(external_id=1, name="Home FC")
        away = Team.objects.create(external_id=2, name="Away FC")
        gameweek = Gameweek.objects.create(number=1, is_scored=True)
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=home, away_team=away,
            kickoff_time=timezone.now(), status=Fixture.Status.FINISHED, home_score=2, away_score=1,
        )
        Prediction.objects.create(user=self.alice, fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=3)
        Prediction.objects.create(user=self.bob, fixture=fixture, predicted_home_score=1, predicted_away_score=1, points=0)

    def test_returns_rank_and_points_for_each_league_the_user_is_in(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get(reverse("league-home-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["public_id"], self.league.public_id)
        self.assertEqual(row["total_points"], 0)
        self.assertEqual(row["rank_display"], "2nd")

    def test_empty_when_the_user_has_no_leagues(self):
        outsider = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")
        self.client.force_authenticate(user=outsider)
        response = self.client.get(reverse("league-home-summary"))
        self.assertEqual(response.data, [])

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("league-home-summary"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LeagueNameValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)

    def test_accepts_a_clean_name_up_to_the_limit(self):
        name = "A" * 32
        response = self.client.post(reverse("league-list-create"), {"name": name})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], name)

    def test_rejects_name_over_32_characters(self):
        response = self.client.post(reverse("league-list-create"), {"name": "A" * 33})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_rejects_blank_name(self):
        response = self.client.post(reverse("league-list-create"), {"name": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_whitespace_only_name(self):
        response = self.client.post(reverse("league-list-create"), {"name": "    "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trims_surrounding_whitespace(self):
        response = self.client.post(reverse("league-list-create"), {"name": "  Office League  "})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Office League")

    def test_rejects_name_containing_profanity(self):
        response = self.client.post(reverse("league-list-create"), {"name": "shit league"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_league_model_also_enforces_profanity_validator_directly(self):
        league = League(name="fuck league", owner=self.user)
        with self.assertRaises(ValidationError):
            league.full_clean()


class PublicLeagueSearchAndFilterTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.other = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.owner)

        self.office_league = League.objects.create(name="Office Sweepstake", owner=self.owner, is_public=True)
        LeagueMembership.objects.create(league=self.office_league, user=self.owner)
        self.friends_league = League.objects.create(
            name="Friends & Family", owner=self.owner, is_public=True, max_members=4
        )
        LeagueMembership.objects.create(league=self.friends_league, user=self.owner)

        old_date = timezone.now() - timedelta(days=30)
        League.objects.filter(pk=self.office_league.pk).update(created_at=old_date)

    def test_search_matches_name_case_insensitively(self):
        response = self.client.get(reverse("league-browse"), {"search": "office"})

        names = [row["name"] for row in response.data]
        self.assertIn("Office Sweepstake", names)
        self.assertNotIn("Friends & Family", names)

    def test_search_with_no_match_returns_empty_list(self):
        response = self.client.get(reverse("league-browse"), {"search": "nonexistent"})
        self.assertEqual(response.data, [])

    def test_default_filter_is_recent_and_orders_newest_first(self):
        response = self.client.get(reverse("league-browse"))

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Friends & Family", "Office Sweepstake"])

    def _fill_up(self, league):
        for n in range(league.max_members - league.memberships.count()):
            member = User.objects.create_user(
                username=f"filler{league.pk}{n}", email=f"filler{league.pk}{n}@example.com", password="pw12345678"
            )
            LeagueMembership.objects.create(league=league, user=member)

    def test_full_leagues_are_always_excluded_regardless_of_filter(self):
        self._fill_up(self.friends_league)
        self.assertEqual(self.friends_league.memberships.count(), self.friends_league.max_members)

        for filter_value in ("recent", "capacity_desc", "capacity_asc"):
            response = self.client.get(reverse("league-browse"), {"filter": filter_value})
            names = [row["name"] for row in response.data]
            self.assertIn("Office Sweepstake", names)
            self.assertNotIn("Friends & Family", names, f"filter={filter_value}")

    def test_a_league_reappears_once_it_is_no_longer_full(self):
        self._fill_up(self.friends_league)
        member = self.friends_league.memberships.exclude(user=self.owner).first().user

        response = self.client.get(reverse("league-browse"))
        self.assertNotIn("Friends & Family", [row["name"] for row in response.data])

        LeagueMembership.objects.filter(league=self.friends_league, user=member).delete()

        response = self.client.get(reverse("league-browse"))
        self.assertIn("Friends & Family", [row["name"] for row in response.data])

    def test_combining_search_and_filter(self):
        response = self.client.get(reverse("league-browse"), {"search": "office", "filter": "recent"})

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Office Sweepstake"])

    def test_filter_capacity_desc_orders_by_max_members_descending(self):
        # office_league defaults to max_members=8, friends_league is 4.
        response = self.client.get(reverse("league-browse"), {"filter": "capacity_desc"})

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Office Sweepstake", "Friends & Family"])

    def test_filter_capacity_asc_orders_by_max_members_ascending(self):
        response = self.client.get(reverse("league-browse"), {"filter": "capacity_asc"})

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Friends & Family", "Office Sweepstake"])

    def test_invalid_filter_value_returns_400(self):
        response = self.client.get(reverse("league-browse"), {"filter": "not-a-real-filter"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vacant_is_no_longer_a_recognised_filter(self):
        response = self.client.get(reverse("league-browse"), {"filter": "vacant"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_browse_listing_never_exposes_who_created_the_league(self):
        response = self.client.get(reverse("league-browse"))
        for row in response.data:
            self.assertNotIn("owner_username", row)

    def test_league_detail_does_expose_who_created_the_league(self):
        response = self.client.get(reverse("league-detail", args=[self.office_league.public_id]))
        self.assertEqual(response.data["owner_username"], "alice")


class LeagueStartingGameweekTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.owner)

    def test_league_created_with_no_gameweeks_synced_has_no_starting_gameweek(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})
        self.assertIsNone(response.data["starting_gameweek"])

    def test_league_records_the_current_gameweek_as_starting_gameweek(self):
        team_a = Team.objects.create(external_id=1, name="Home FC")
        team_b = Team.objects.create(external_id=2, name="Away FC")
        past_gw = Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=7), is_scored=True)
        upcoming_gw = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))
        for number, gw in ((1, past_gw), (2, upcoming_gw)):
            Fixture.objects.create(
                external_id=number, gameweek=gw, home_team=team_a, away_team=team_b,
                kickoff_time=timezone.now(),
            )

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertEqual(response.data["starting_gameweek"], 2)

    def test_starting_gameweek_runs_past_the_season_once_every_gameweek_is_scored(self):
        team_a = Team.objects.create(external_id=1, name="Home FC")
        team_b = Team.objects.create(external_id=2, name="Away FC")
        gw = Gameweek.objects.create(number=38, deadline=timezone.now() - timedelta(days=1), is_scored=True)
        Fixture.objects.create(
            external_id=1, gameweek=gw, home_team=team_a, away_team=team_b, kickoff_time=timezone.now(),
        )

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        # Gameweek 38 has already been played and scored, so a league created
        # now can't count it - there's nothing left this season to count.
        self.assertEqual(response.data["starting_gameweek"], 39)

    def test_league_created_after_the_deadline_starts_from_the_next_gameweek(self):
        team_a = Team.objects.create(external_id=1, name="Home FC")
        team_b = Team.objects.create(external_id=2, name="Away FC")
        in_progress = Gameweek.objects.create(number=2, deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=3, deadline=timezone.now() + timedelta(days=7))
        Fixture.objects.create(
            external_id=1, gameweek=in_progress, home_team=team_a, away_team=team_b,
            kickoff_time=timezone.now(),
        )

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertEqual(response.data["starting_gameweek"], 3)

    def test_the_owners_membership_starts_from_the_same_gameweek_as_the_league(self):
        Gameweek.objects.create(number=4, deadline=timezone.now() + timedelta(days=2))

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        membership = LeagueMembership.objects.get(league__public_id=response.data["public_id"])
        self.assertEqual(membership.starting_gameweek, 4)
        self.assertEqual(response.data["starting_gameweek"], 4)

    def test_a_member_joining_later_records_their_own_starting_gameweek(self):
        Gameweek.objects.create(number=4, deadline=timezone.now() + timedelta(days=2))
        created = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        # Gameweek 4 locks and 5 opens, then someone else joins.
        Gameweek.objects.filter(number=4).update(deadline=timezone.now() - timedelta(hours=1))
        Gameweek.objects.create(number=5, deadline=timezone.now() + timedelta(days=7))
        joiner = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.client.force_authenticate(user=joiner)
        self.client.post(reverse("league-join"), {"code": created.data["code"]})

        membership = LeagueMembership.objects.get(league__public_id=created.data["public_id"], user=joiner)
        self.assertEqual(membership.starting_gameweek, 5)

    def test_browse_listing_includes_starting_gameweek(self):
        gw = Gameweek.objects.create(number=5, deadline=timezone.now() + timedelta(days=1))
        League.objects.create(name="Public League", owner=self.owner, is_public=True, starting_gameweek=gw.number)

        response = self.client.get(reverse("league-browse"))

        row = next(r for r in response.data if r["name"] == "Public League")
        self.assertEqual(row["starting_gameweek"], 5)


class LeagueScoringStartsFromJoinTests(APITestCase):
    """A league only counts the gameweeks from each member's own join
    onwards, so creating or joining one never carries an existing total in."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def _gameweek(self, number, deadline, *, is_scored=False, finished=False):
        gameweek = Gameweek.objects.create(number=number, deadline=deadline, is_scored=is_scored)
        fixture = Fixture.objects.create(
            external_id=number, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=deadline + timedelta(hours=1),
            status=Fixture.Status.FINISHED if finished else Fixture.Status.SCHEDULED,
            home_score=2 if finished else None,
            away_score=1 if finished else None,
        )
        return gameweek, fixture

    def _predict(self, user, fixture, points=None):
        return Prediction.objects.create(
            user=user, fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=points
        )

    def _create_league(self, user, name="Fresh Start"):
        self.client.force_authenticate(user=user)
        return self.client.post(reverse("league-list-create"), {"name": name})

    def _standing(self, public_id, username):
        response = self.client.get(reverse("league-detail", args=[public_id]))
        return next(row for row in response.data["standings"] if row["username"] == username)

    def test_creating_a_league_after_scoring_points_starts_the_owner_on_zero(self):
        _, played = self._gameweek(1, timezone.now() - timedelta(days=7), is_scored=True, finished=True)
        self._predict(self.alice, played, points=5)
        self._gameweek(2, timezone.now() + timedelta(days=2))

        created = self._create_league(self.alice)

        self.assertEqual(created.data["starting_gameweek"], 2)
        self.assertEqual(self._standing(created.data["public_id"], "alice")["total_points"], 0)

    def test_points_from_the_starting_gameweek_onwards_do_count(self):
        _, played = self._gameweek(1, timezone.now() - timedelta(days=7), is_scored=True, finished=True)
        self._predict(self.alice, played, points=5)
        _, upcoming = self._gameweek(2, timezone.now() + timedelta(days=2))

        created = self._create_league(self.alice)

        # Gameweek 2 is then played and officially scored.
        self._predict(self.alice, upcoming, points=4)
        Gameweek.objects.filter(number=2).update(is_scored=True)

        self.assertEqual(self._standing(created.data["public_id"], "alice")["total_points"], 4)

    def test_joining_later_leaves_the_earlier_gameweeks_out_of_the_total(self):
        _, first = self._gameweek(1, timezone.now() - timedelta(days=14), is_scored=True, finished=True)
        self._predict(self.alice, first, points=5)
        self._predict(self.bob, first, points=9)
        _, second = self._gameweek(2, timezone.now() + timedelta(days=2))

        created = self._create_league(self.alice)

        # Gameweek 2 locks, is played and scored, and gameweek 3 opens.
        self._predict(self.alice, second, points=3)
        self._predict(self.bob, second, points=7)
        Gameweek.objects.filter(number=2).update(is_scored=True, deadline=timezone.now() - timedelta(hours=1))
        self._gameweek(3, timezone.now() + timedelta(days=7))

        self.client.force_authenticate(user=self.bob)
        self.client.post(reverse("league-join"), {"code": created.data["code"]})

        public_id = created.data["public_id"]
        self.assertEqual(self._standing(public_id, "alice")["total_points"], 3)
        # Bob's 16 points across gameweeks 1 and 2 both predate his join.
        self.assertEqual(self._standing(public_id, "bob")["total_points"], 0)
        self.assertEqual(self._standing(public_id, "bob")["starting_gameweek"], 3)

    def test_live_current_gameweek_points_only_count_from_the_join_gameweek(self):
        _, live_fixture = self._gameweek(1, timezone.now() + timedelta(days=1))
        created = self._create_league(self.alice)

        # Gameweek 1 kicks off and its only fixture finishes, still unscored.
        Gameweek.objects.filter(number=1).update(deadline=timezone.now() - timedelta(hours=4))
        Fixture.objects.filter(pk=live_fixture.pk).update(
            status=Fixture.Status.FINISHED, home_score=2, away_score=1,
            kickoff_time=timezone.now() - timedelta(hours=3),
        )
        self._predict(self.alice, live_fixture)
        self._predict(self.bob, live_fixture)
        self._gameweek(2, timezone.now() + timedelta(days=7))

        self.client.force_authenticate(user=self.bob)
        self.client.post(reverse("league-join"), {"code": created.data["code"]})

        public_id = created.data["public_id"]
        self.assertEqual(self._standing(public_id, "alice")["current_gameweek_points"], 3)
        # Bob predicted the same scoreline, but joined for gameweek 2 onwards.
        self.assertEqual(self._standing(public_id, "bob")["current_gameweek_points"], 0)
        # ...so his gameweek column is "not yet", not a score of nil.
        self.assertFalse(self._standing(public_id, "bob")["current_gameweek_counts"])
        self.assertTrue(self._standing(public_id, "alice")["current_gameweek_counts"])

    def test_a_member_with_no_gameweek_behind_them_yet_has_nothing_counted(self):
        _, first = self._gameweek(1, timezone.now() - timedelta(days=14), is_scored=True, finished=True)
        self._predict(self.alice, first, points=5)
        _, second = self._gameweek(2, timezone.now() + timedelta(days=2))

        created = self._create_league(self.alice)

        self._predict(self.alice, second, points=3)
        Gameweek.objects.filter(number=2).update(is_scored=True, deadline=timezone.now() - timedelta(hours=1))
        self._gameweek(3, timezone.now() + timedelta(days=7))

        self.client.force_authenticate(user=self.bob)
        self.client.post(reverse("league-join"), {"code": created.data["code"]})

        public_id = created.data["public_id"]
        # Nothing has been scored since bob joined for gameweek 3.
        self.assertFalse(self._standing(public_id, "bob")["has_counted_gameweeks"])
        self.assertTrue(self._standing(public_id, "alice")["has_counted_gameweeks"])

    def test_the_gameweek_column_reads_as_nothing_until_it_kicks_off(self):
        # A gameweek nobody has played yet isn't a score of nil for anyone.
        self._gameweek(1, timezone.now() + timedelta(days=2))

        created = self._create_league(self.alice)

        self.assertFalse(self._standing(created.data["public_id"], "alice")["current_gameweek_counts"])

    def test_home_summary_flags_a_league_with_nothing_counted_yet(self):
        self._gameweek(1, timezone.now() - timedelta(days=7), is_scored=True)
        self._gameweek(2, timezone.now() + timedelta(days=2))

        self._create_league(self.alice)

        self.assertFalse(self.client.get(reverse("league-home-summary")).data[0]["has_counted_gameweeks"])

    def test_my_league_listings_use_the_same_starting_point(self):
        _, played = self._gameweek(1, timezone.now() - timedelta(days=7), is_scored=True, finished=True)
        self._predict(self.alice, played, points=5)
        self._gameweek(2, timezone.now() + timedelta(days=2))

        self._create_league(self.alice)

        summary = self.client.get(reverse("league-home-summary")).data[0]
        listed = self.client.get(reverse("league-list-create")).data[0]
        self.assertEqual(summary["total_points"], 0)
        self.assertEqual(listed["total_points"], 0)

    def test_memberships_predating_gameweek_tracking_still_count_everything(self):
        _, played = self._gameweek(1, timezone.now() - timedelta(days=7), is_scored=True, finished=True)
        self._predict(self.alice, played, points=5)
        league = League.objects.create(name="Legacy League", owner=self.alice)
        LeagueMembership.objects.create(league=league, user=self.alice, starting_gameweek=None)

        self.client.force_authenticate(user=self.alice)
        self.assertEqual(self._standing(league.public_id, "alice")["total_points"], 5)


class LeagueMemberRecordTests(APITestCase):
    """The per-player breakdown behind a league's standings, and the view of
    another member's predictions for one of its gameweeks."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.eve = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

        # The league starts at gameweek 2; bob only joins for gameweek 3.
        self.league = League.objects.create(name="Office League", owner=self.alice, starting_gameweek=2)
        LeagueMembership.objects.create(league=self.league, user=self.alice, starting_gameweek=2)
        LeagueMembership.objects.create(league=self.league, user=self.bob, starting_gameweek=3)

        for number, points in ((1, {"alice": 5, "bob": 9}), (2, {"alice": 4, "bob": 6}), (3, {"alice": 2, "bob": 7})):
            _, fixture = self._gameweek(
                number, timezone.now() - timedelta(days=14 - number), is_scored=True, finished=True
            )
            for username, value in points.items():
                self._predict(getattr(self, username), fixture, points=value)

        # Gameweek 4 is under way: locked, one finished fixture, not yet scored.
        _, self.live_fixture = self._gameweek(4, timezone.now() - timedelta(hours=2), finished=True)
        self._predict(self.alice, self.live_fixture)

    def _gameweek(self, number, deadline, *, is_scored=False, finished=False):
        gameweek = Gameweek.objects.create(number=number, deadline=deadline, is_scored=is_scored)
        fixture = Fixture.objects.create(
            external_id=number, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=deadline + timedelta(hours=1),
            status=Fixture.Status.FINISHED if finished else Fixture.Status.SCHEDULED,
            home_score=2 if finished else None,
            away_score=1 if finished else None,
        )
        return gameweek, fixture

    def _predict(self, user, fixture, points=None):
        return Prediction.objects.create(
            user=user, fixture=fixture, predicted_home_score=2, predicted_away_score=1, points=points
        )

    def _member(self, viewer, subject):
        self.client.force_authenticate(user=viewer)
        return self.client.get(reverse("league-member-detail", args=[self.league.public_id, subject.id]))

    def _gameweek_view(self, viewer, subject, number):
        self.client.force_authenticate(user=viewer)
        return self.client.get(
            reverse("league-member-gameweek", args=[self.league.public_id, subject.id, number])
        )

    def test_lists_each_gameweek_from_the_members_own_start_to_the_current_one(self):
        response = self._member(self.alice, self.alice)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["gameweek"] for row in response.data["gameweeks"]], [2, 3, 4])
        self.assertEqual([row["points"] for row in response.data["gameweeks"]], [4, 2, 3])
        self.assertEqual(response.data["total_points"], 6)
        self.assertEqual(response.data["current_gameweek_points"], 3)
        self.assertEqual(response.data["starting_gameweek"], 2)

    def test_a_later_joiner_only_sees_their_own_span(self):
        response = self._member(self.alice, self.bob)

        self.assertEqual([row["gameweek"] for row in response.data["gameweeks"]], [3, 4])
        self.assertEqual(response.data["username"], "bob")
        self.assertEqual(response.data["starting_gameweek"], 3)
        # Gameweeks 1 and 2 are excluded, so only gameweek 3's 7 points count.
        self.assertEqual(response.data["total_points"], 7)

    def test_flags_which_gameweeks_have_predictions_to_look_at(self):
        rows = {row["gameweek"]: row for row in self._member(self.alice, self.bob).data["gameweeks"]}

        self.assertTrue(rows[3]["has_predictions"])
        self.assertTrue(rows[3]["predictions_visible"])
        self.assertFalse(rows[4]["has_predictions"])

    def test_reports_the_league_and_whether_it_is_you(self):
        response = self._member(self.bob, self.alice)

        self.assertEqual(response.data["league"]["name"], "Office League")
        self.assertEqual(response.data["league"]["public_id"], self.league.public_id)
        self.assertFalse(response.data["is_you"])
        self.assertTrue(self._member(self.alice, self.alice).data["is_you"])

    def _postpone_gameweek_four(self, *, deadline, kickoff):
        """Move gameweek 4 (and its only fixture) around in time."""
        Gameweek.objects.filter(number=4).update(deadline=deadline)
        Fixture.objects.filter(pk=self.live_fixture.pk).update(kickoff_time=kickoff)

    def test_predictions_stay_hidden_until_the_gameweek_kicks_off(self):
        self._postpone_gameweek_four(
            deadline=timezone.now() + timedelta(days=1), kickoff=timezone.now() + timedelta(days=1, hours=1)
        )

        rows = {row["gameweek"]: row for row in self._member(self.bob, self.alice).data["gameweeks"]}

        self.assertFalse(rows[4]["predictions_visible"])
        self.assertFalse(rows[4]["has_started"])
        self.assertTrue(rows[3]["predictions_visible"])

    def test_predictions_stay_hidden_in_the_gap_between_the_deadline_and_kickoff(self):
        # Predictions have locked, but the first match hasn't kicked off yet -
        # still nobody else's business.
        self._postpone_gameweek_four(
            deadline=timezone.now() - timedelta(minutes=30), kickoff=timezone.now() + timedelta(minutes=30)
        )

        rows = {row["gameweek"]: row for row in self._member(self.bob, self.alice).data["gameweeks"]}

        self.assertFalse(rows[4]["predictions_visible"])

    def test_you_can_always_see_your_own_predictions(self):
        self._postpone_gameweek_four(
            deadline=timezone.now() + timedelta(days=1), kickoff=timezone.now() + timedelta(days=1, hours=1)
        )

        rows = {row["gameweek"]: row for row in self._member(self.alice, self.alice).data["gameweeks"]}

        self.assertTrue(rows[4]["predictions_visible"])
        self.assertEqual(self._gameweek_view(self.alice, self.alice, 4).status_code, status.HTTP_200_OK)

    def test_reports_career_totals_alongside_the_league_ones(self):
        response = self._member(self.bob, self.alice)

        # Alice has 5 + 4 + 2 across three scored gameweeks, but only 4 + 2
        # of those count in this league.
        self.assertEqual(response.data["career_points"], 11)
        self.assertEqual(response.data["career_gameweeks"], 3)
        self.assertEqual(response.data["average_points"], 3.7)
        self.assertEqual(response.data["total_points"], 6)

    def test_average_is_absent_when_nothing_has_been_scored_yet(self):
        loner = User.objects.create_user(username="newbie", email="newbie@example.com", password="pw12345678")
        LeagueMembership.objects.create(league=self.league, user=loner, starting_gameweek=4)

        response = self._member(self.alice, loner)

        self.assertEqual(response.data["career_points"], 0)
        self.assertEqual(response.data["career_gameweeks"], 0)
        self.assertIsNone(response.data["average_points"])
        self.assertFalse(response.data["has_counted_gameweeks"])

    def test_empty_record_for_a_league_that_starts_in_a_future_gameweek(self):
        LeagueMembership.objects.filter(league=self.league, user=self.bob).update(starting_gameweek=5)

        response = self._member(self.bob, self.bob)

        self.assertEqual(response.data["gameweeks"], [])
        self.assertEqual(response.data["total_points"], 0)
        self.assertEqual(response.data["starting_gameweek"], 5)

    def test_non_members_cannot_see_a_members_record(self):
        response = self._member(self.eve, self.alice)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_someone_outside_the_league_is_not_a_member_to_look_up(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-member-detail", args=[self.league.public_id, self.eve.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        response = self.client.get(reverse("league-member-detail", args=[self.league.public_id, self.alice.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_members_can_see_each_others_predictions_for_a_locked_gameweek(self):
        response = self._gameweek_view(self.bob, self.alice, 2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")
        self.assertEqual(response.data["points"], 4)
        prediction = response.data["fixtures"][0]["prediction"]
        self.assertEqual(prediction["predicted_home_score"], 2)
        self.assertEqual(prediction["predicted_away_score"], 1)

    def test_live_points_for_the_gameweek_in_progress(self):
        response = self._gameweek_view(self.bob, self.alice, 4)

        self.assertEqual(response.data["points"], 3)
        self.assertFalse(response.data["is_scored"])

    def test_cannot_see_predictions_for_a_gameweek_before_they_joined(self):
        response = self._gameweek_view(self.alice, self.bob, 2)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("before bob joined", response.data["detail"])

    def test_cannot_see_another_members_predictions_before_kickoff(self):
        self._postpone_gameweek_four(
            deadline=timezone.now() - timedelta(minutes=30), kickoff=timezone.now() + timedelta(minutes=30)
        )

        response = self._gameweek_view(self.bob, self.alice, 4)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("kicks off", response.data["detail"])

    def test_non_members_cannot_see_predictions(self):
        response = self._gameweek_view(self.eve, self.alice, 2)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_gameweek_is_a_404(self):
        response = self._gameweek_view(self.alice, self.alice, 99)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
