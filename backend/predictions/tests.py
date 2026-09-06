from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from backend.fixtures.models import Fixture, Gameweek, Team

from .models import Prediction
from .scoring import calculate_points

User = get_user_model()


class ScoringTests(TestCase):
    def test_exact_score_under_five_goals_awards_three_points(self):
        self.assertEqual(calculate_points(2, 1, 2, 1), 3)

    def test_exact_score_with_five_or_more_goals_awards_four_points(self):
        self.assertEqual(calculate_points(3, 2, 3, 2), 4)
        self.assertEqual(calculate_points(5, 1, 5, 1), 4)

    def test_exact_draw_scores_correctly(self):
        self.assertEqual(calculate_points(1, 1, 1, 1), 3)
        self.assertEqual(calculate_points(0, 0, 0, 0), 3)

    def test_correct_result_wrong_score_awards_one_point(self):
        self.assertEqual(calculate_points(1, 0, 3, 1), 1)  # home win either way
        self.assertEqual(calculate_points(0, 2, 1, 3), 1)  # away win either way
        self.assertEqual(calculate_points(1, 1, 2, 2), 1)  # draw either way

    def test_wrong_result_awards_zero_points(self):
        self.assertEqual(calculate_points(1, 0, 0, 1), 0)
        self.assertEqual(calculate_points(2, 2, 1, 0), 0)


class GameweekPredictionsViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)

        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def _make_gameweek(self, deadline_delta):
        gameweek = Gameweek.objects.create(number=1, deadline=timezone.now() + deadline_delta)
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )
        return gameweek, fixture

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("gameweek-predictions", args=[1]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_fixtures_with_no_prediction_initially(self):
        self._make_gameweek(timedelta(hours=1))
        response = self.client.get(reverse("gameweek-predictions", args=[1]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_locked"])
        self.assertEqual(len(response.data["fixtures"]), 1)
        self.assertIsNone(response.data["fixtures"][0]["prediction"])

    def test_unknown_gameweek_returns_404(self):
        response = self.client.get(reverse("gameweek-predictions", args=[999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_can_submit_predictions_before_deadline(self):
        gameweek, fixture = self._make_gameweek(timedelta(hours=1))

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {"predictions": [{"fixture_id": fixture.id, "home_score": 2, "away_score": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prediction = Prediction.objects.get(user=self.user, fixture=fixture)
        self.assertEqual(prediction.predicted_home_score, 2)
        self.assertEqual(prediction.predicted_away_score, 1)

    def test_resubmitting_updates_existing_prediction_instead_of_duplicating(self):
        gameweek, fixture = self._make_gameweek(timedelta(hours=1))
        payload = {"predictions": [{"fixture_id": fixture.id, "home_score": 2, "away_score": 1}]}
        self.client.post(reverse("gameweek-predictions", args=[1]), payload, format="json")

        payload["predictions"][0]["home_score"] = 4
        self.client.post(reverse("gameweek-predictions", args=[1]), payload, format="json")

        self.assertEqual(Prediction.objects.filter(user=self.user, fixture=fixture).count(), 1)
        self.assertEqual(Prediction.objects.get(user=self.user, fixture=fixture).predicted_home_score, 4)

    def test_cannot_submit_predictions_after_deadline(self):
        gameweek, fixture = self._make_gameweek(-timedelta(hours=1))

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {"predictions": [{"fixture_id": fixture.id, "home_score": 2, "away_score": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Prediction.objects.filter(fixture=fixture).exists())

    def test_cannot_predict_fixture_outside_gameweek(self):
        gameweek, fixture = self._make_gameweek(timedelta(hours=1))
        other_gameweek = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(hours=1))
        other_fixture = Fixture.objects.create(
            external_id=2, gameweek=other_gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {"predictions": [{"fixture_id": other_fixture.id, "home_score": 1, "away_score": 0}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_negative_scores(self):
        gameweek, fixture = self._make_gameweek(timedelta(hours=1))

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {"predictions": [{"fixture_id": fixture.id, "home_score": -1, "away_score": 0}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_submission_is_rejected(self):
        gameweek = Gameweek.objects.create(number=1, deadline=timezone.now() + timedelta(hours=1))
        fixture_a = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )
        fixture_b = Fixture.objects.create(
            external_id=2, gameweek=gameweek, home_team=self.away, away_team=self.home,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {"predictions": [{"fixture_id": fixture_a.id, "home_score": 2, "away_score": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Prediction.objects.filter(user=self.user, fixture=fixture_a).exists())
        self.assertFalse(Prediction.objects.filter(user=self.user, fixture=fixture_b).exists())

    def test_can_submit_once_every_fixture_has_a_prediction(self):
        gameweek = Gameweek.objects.create(number=1, deadline=timezone.now() + timedelta(hours=1))
        fixture_a = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )
        fixture_b = Fixture.objects.create(
            external_id=2, gameweek=gameweek, home_team=self.away, away_team=self.home,
            kickoff_time=timezone.now() + timedelta(hours=2),
        )

        response = self.client.post(
            reverse("gameweek-predictions", args=[1]),
            {
                "predictions": [
                    {"fixture_id": fixture_a.id, "home_score": 2, "away_score": 1},
                    {"fixture_id": fixture_b.id, "home_score": 0, "away_score": 0},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Prediction.objects.filter(user=self.user, fixture=fixture_a).exists())
        self.assertTrue(Prediction.objects.filter(user=self.user, fixture=fixture_b).exists())

    def test_only_the_next_gameweek_to_lock_can_be_predicted(self):
        # Gameweek 1 is the very next to lock; gameweek 2's own deadline
        # hasn't passed either, but it isn't the *next* one - only one
        # gameweek should ever be predictable at a time.
        gameweek1, fixture1 = self._make_gameweek(timedelta(hours=1))
        gameweek2 = Gameweek.objects.create(number=2, deadline=timezone.now() + timedelta(days=7))
        fixture2 = Fixture.objects.create(
            external_id=2, gameweek=gameweek2, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() + timedelta(days=7, hours=1),
        )

        get_gw1 = self.client.get(reverse("gameweek-predictions", args=[1]))
        get_gw2 = self.client.get(reverse("gameweek-predictions", args=[2]))
        self.assertFalse(get_gw1.data["is_locked"])
        self.assertTrue(get_gw2.data["is_locked"])

        response = self.client.post(
            reverse("gameweek-predictions", args=[2]),
            {"predictions": [{"fixture_id": fixture2.id, "home_score": 1, "away_score": 0}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Prediction.objects.filter(fixture=fixture2).exists())

    def test_a_past_gameweek_is_reported_as_locked_for_predictions(self):
        past_gameweek = Gameweek.objects.create(
            number=1, deadline=timezone.now() - timedelta(days=7), is_scored=True,
        )
        Fixture.objects.create(
            external_id=1, gameweek=past_gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(days=7),
            status=Fixture.Status.FINISHED, home_score=1, away_score=0,
        )

        response = self.client.get(reverse("gameweek-predictions", args=[1]))

        self.assertTrue(response.data["is_locked"])


class MyPredictionHistoryViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def test_only_counts_scored_gameweeks(self):
        scored_gw = Gameweek.objects.create(number=1, is_scored=True)
        unscored_gw = Gameweek.objects.create(number=2, is_scored=False)
        scored_fixture = Fixture.objects.create(
            external_id=1, gameweek=scored_gw, home_team=self.home, away_team=self.away, kickoff_time=timezone.now(),
        )
        unscored_fixture = Fixture.objects.create(
            external_id=2, gameweek=unscored_gw, home_team=self.home, away_team=self.away, kickoff_time=timezone.now(),
        )
        Prediction.objects.create(user=self.user, fixture=scored_fixture, predicted_home_score=1, predicted_away_score=0, points=3)
        Prediction.objects.create(user=self.user, fixture=unscored_fixture, predicted_home_score=1, predicted_away_score=0, points=None)

        response = self.client.get(reverse("prediction-history"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall_total"], 3)
        self.assertEqual(response.data["by_gameweek"], [{"gameweek": 1, "points": 3}])


class ScoreGameweeksCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        self.home = Team.objects.create(external_id=1, name="Home FC")
        self.away = Team.objects.create(external_id=2, name="Away FC")

    def test_finalizes_gameweek_and_scores_predictions(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() - timedelta(minutes=1))
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=3), status=Fixture.Status.FINISHED,
            home_score=3, away_score=1,
        )
        exact = Prediction.objects.create(user=self.user, fixture=fixture, predicted_home_score=3, predicted_away_score=1)
        wrong = Prediction.objects.create(user=self.other_user, fixture=fixture, predicted_home_score=0, predicted_away_score=0)

        call_command("score_gameweeks")

        gameweek.refresh_from_db()
        exact.refresh_from_db()
        wrong.refresh_from_db()
        self.assertTrue(gameweek.is_scored)
        self.assertEqual(exact.points, 3)
        self.assertEqual(wrong.points, 0)

    def test_awards_four_points_for_high_scoring_exact_prediction(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() - timedelta(minutes=1))
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=3), status=Fixture.Status.FINISHED,
            home_score=5, away_score=1,
        )
        prediction = Prediction.objects.create(user=self.user, fixture=fixture, predicted_home_score=5, predicted_away_score=1)

        call_command("score_gameweeks")

        prediction.refresh_from_db()
        self.assertEqual(prediction.points, 4)

    def test_does_not_score_gameweek_before_finalize_after(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() + timedelta(hours=1))
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=1), status=Fixture.Status.FINISHED,
            home_score=1, away_score=0,
        )
        prediction = Prediction.objects.create(user=self.user, fixture=fixture, predicted_home_score=1, predicted_away_score=0)

        call_command("score_gameweeks")

        gameweek.refresh_from_db()
        prediction.refresh_from_db()
        self.assertFalse(gameweek.is_scored)
        self.assertIsNone(prediction.points)

    def test_does_not_score_gameweek_with_unfinished_fixture(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() - timedelta(minutes=1))
        Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=1), status=Fixture.Status.SCHEDULED,
        )

        call_command("score_gameweeks")

        gameweek.refresh_from_db()
        self.assertFalse(gameweek.is_scored)

    def test_ignores_postponed_fixtures_when_checking_completeness(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() - timedelta(minutes=1))
        finished = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=3), status=Fixture.Status.FINISHED,
            home_score=1, away_score=0,
        )
        Fixture.objects.create(
            external_id=2, gameweek=gameweek, home_team=self.away, away_team=self.home,
            kickoff_time=timezone.now() - timedelta(hours=3), status=Fixture.Status.POSTPONED,
        )
        prediction = Prediction.objects.create(user=self.user, fixture=finished, predicted_home_score=1, predicted_away_score=0)

        call_command("score_gameweeks")

        gameweek.refresh_from_db()
        prediction.refresh_from_db()
        self.assertTrue(gameweek.is_scored)
        self.assertEqual(prediction.points, 3)

    def test_does_not_rescore_already_scored_predictions(self):
        gameweek = Gameweek.objects.create(number=1, finalize_after=timezone.now() - timedelta(minutes=1), is_scored=True)
        fixture = Fixture.objects.create(
            external_id=1, gameweek=gameweek, home_team=self.home, away_team=self.away,
            kickoff_time=timezone.now() - timedelta(hours=3), status=Fixture.Status.FINISHED,
            home_score=1, away_score=0,
        )
        prediction = Prediction.objects.create(user=self.user, fixture=fixture, predicted_home_score=1, predicted_away_score=0, points=3)

        call_command("score_gameweeks")

        prediction.refresh_from_db()
        self.assertEqual(prediction.points, 3)
