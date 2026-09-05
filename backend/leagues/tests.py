from django.contrib.auth import get_user_model
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

    def test_creator_is_automatically_a_member(self):
        response = self.client.post(reverse("league-list-create"), {"name": "Office League"})
        league = League.objects.get(id=response.data["id"])

        self.assertTrue(LeagueMembership.objects.filter(league=league, user=self.user).exists())
        self.assertEqual(response.data["member_count"], 1)
        self.assertEqual(response.data["owner_username"], "alice")

    def test_league_codes_are_unique(self):
        r1 = self.client.post(reverse("league-list-create"), {"name": "League One"})
        r2 = self.client.post(reverse("league-list-create"), {"name": "League Two"})
        self.assertNotEqual(r1.data["code"], r2.data["code"])

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


class JoinLeagueTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.joiner = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.league = League.objects.create(name="Office League", owner=self.owner)
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
        response = self.client.get(reverse("league-detail", args=[self.league.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        standings = response.data["standings"]
        self.assertEqual(standings[0]["username"], "alice")
        self.assertEqual(standings[0]["total_points"], 3)
        self.assertEqual(standings[1]["username"], "bob")
        self.assertEqual(standings[1]["total_points"], 0)

    def test_is_owner_flag(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get(reverse("league-detail", args=[self.league.id]))
        self.assertFalse(response.data["is_owner"])

        self.client.force_authenticate(user=self.alice)
        response = self.client.get(reverse("league-detail", args=[self.league.id]))
        self.assertTrue(response.data["is_owner"])

    def test_non_member_cannot_view_league(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(reverse("league-detail", args=[self.league.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
