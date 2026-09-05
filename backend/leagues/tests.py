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

    def test_browse_listing_flags_full_leagues(self):
        LeagueMembership.objects.create(league=self.public_league, user=self.viewer)
        other_user = User.objects.create_user(username="eve", email="eve@example.com", password="pw12345678")
        self.client.force_authenticate(user=other_user)

        response = self.client.get(reverse("league-browse"))
        row = next(r for r in response.data if r["public_id"] == self.public_league.public_id)

        self.assertTrue(row["is_full"])

    def test_browse_listing_flags_leagues_i_have_already_joined(self):
        LeagueMembership.objects.create(league=self.public_league, user=self.viewer)

        response = self.client.get(reverse("league-browse"))
        row = next(r for r in response.data if r["public_id"] == self.public_league.public_id)

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

    def test_filter_vacant_excludes_full_leagues(self):
        for n in range(3):
            member = User.objects.create_user(username=f"filler{n}", email=f"filler{n}@example.com", password="pw12345678")
            LeagueMembership.objects.create(league=self.friends_league, user=member)
        self.assertEqual(self.friends_league.memberships.count(), self.friends_league.max_members)

        response = self.client.get(reverse("league-browse"), {"filter": "vacant"})

        names = [row["name"] for row in response.data]
        self.assertIn("Office Sweepstake", names)
        self.assertNotIn("Friends & Family", names)

    def test_combining_search_and_vacant_filter(self):
        response = self.client.get(reverse("league-browse"), {"search": "office", "filter": "vacant"})

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Office Sweepstake"])

    def test_invalid_filter_value_returns_400(self):
        response = self.client.get(reverse("league-browse"), {"filter": "not-a-real-filter"})
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

    def test_league_records_the_next_unlocked_gameweek_as_starting_gameweek(self):
        team_a = Team.objects.create(external_id=1, name="Home FC")
        team_b = Team.objects.create(external_id=2, name="Away FC")
        past_gw = Gameweek.objects.create(number=1, deadline=timezone.now() - timedelta(days=7))
        upcoming_gw = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))
        for number, gw in ((1, past_gw), (2, upcoming_gw)):
            Fixture.objects.create(
                external_id=number, gameweek=gw, home_team=team_a, away_team=team_b,
                kickoff_time=timezone.now(),
            )

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertEqual(response.data["starting_gameweek"], 2)

    def test_starting_gameweek_falls_back_to_most_recent_once_season_is_over(self):
        team_a = Team.objects.create(external_id=1, name="Home FC")
        team_b = Team.objects.create(external_id=2, name="Away FC")
        gw = Gameweek.objects.create(number=38, deadline=timezone.now() - timedelta(days=1))
        Fixture.objects.create(
            external_id=1, gameweek=gw, home_team=team_a, away_team=team_b, kickoff_time=timezone.now(),
        )

        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertEqual(response.data["starting_gameweek"], 38)

    def test_browse_listing_includes_starting_gameweek(self):
        gw = Gameweek.objects.create(number=5, deadline=timezone.now() + timedelta(days=1))
        League.objects.create(name="Public League", owner=self.owner, is_public=True, starting_gameweek=gw.number)

        response = self.client.get(reverse("league-browse"))

        row = next(r for r in response.data if r["name"] == "Public League")
        self.assertEqual(row["starting_gameweek"], 5)
