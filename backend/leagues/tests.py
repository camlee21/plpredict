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

    def test_league_defaults_to_private_with_eight_max_members(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})

        self.assertFalse(response.data["is_public"])
        self.assertEqual(response.data["max_members"], 8)

    def test_can_create_public_league_with_custom_max_members(self):
        response = self.client.post(
            reverse("league-list-create"),
            {"name": "Open League", "is_public": True, "max_members": 32},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_public"])
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
        self.client.force_authenticate(user=self.owner)

        self.office_league = League.objects.create(name="Office Sweepstake", owner=self.owner, is_public=True)
        LeagueMembership.objects.create(league=self.office_league, user=self.owner)
        self.friends_league = League.objects.create(name="Friends & Family", owner=self.owner, is_public=True)
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

    def test_filter_by_created_after(self):
        cutoff = (timezone.now() - timedelta(days=1)).date().isoformat()
        response = self.client.get(reverse("league-browse"), {"created_after": cutoff})

        names = [row["name"] for row in response.data]
        self.assertIn("Friends & Family", names)
        self.assertNotIn("Office Sweepstake", names)

    def test_filter_by_created_before(self):
        cutoff = (timezone.now() - timedelta(days=1)).date().isoformat()
        response = self.client.get(reverse("league-browse"), {"created_before": cutoff})

        names = [row["name"] for row in response.data]
        self.assertIn("Office Sweepstake", names)
        self.assertNotIn("Friends & Family", names)

    def test_combining_search_and_date_filters(self):
        cutoff = (timezone.now() - timedelta(days=1)).date().isoformat()
        response = self.client.get(
            reverse("league-browse"), {"search": "office", "created_before": cutoff}
        )

        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Office Sweepstake"])

    def test_invalid_date_format_returns_400(self):
        response = self.client.get(reverse("league-browse"), {"created_after": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
