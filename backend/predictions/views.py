from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.fixtures.models import Gameweek, current_gameweek_number, next_predictable_gameweek_number

from .models import Prediction
from .serializers import BulkPredictionSerializer, FixtureWithPredictionSerializer


class GameweekPredictionsView(APIView):
    """Fetch or submit the current user's predictions for one gameweek.

    Only the single next gameweek to lock (the one `next_predictable_gameweek_number`
    returns) can be predicted for at any given time - not any gameweek whose
    own deadline merely hasn't passed yet, and not a past one. Every other
    gameweek is reported as locked, read-only."""

    permission_classes = [IsAuthenticated]

    def get(self, request, number):
        gameweek = get_object_or_404(Gameweek, number=number)
        fixtures = list(gameweek.matches.select_related("home_team", "away_team"))
        my_predictions = Prediction.objects.filter(user=request.user, fixture__gameweek=gameweek)
        predictions_by_fixture = {p.fixture_id: p for p in my_predictions}

        serializer = FixtureWithPredictionSerializer(
            fixtures, many=True, context={"predictions_by_fixture": predictions_by_fixture}
        )
        is_locked = number != next_predictable_gameweek_number()
        if gameweek.is_scored:
            lifecycle = "previous"
        elif number == current_gameweek_number():
            lifecycle = "current"
        else:
            lifecycle = "future"
        return Response(
            {
                "gameweek": number,
                "deadline": gameweek.deadline,
                "is_locked": is_locked,
                "is_scored": gameweek.is_scored,
                "lifecycle": lifecycle,
                "fixtures": serializer.data,
            }
        )

    def post(self, request, number):
        gameweek = get_object_or_404(Gameweek, number=number)
        if number != next_predictable_gameweek_number():
            return Response(
                {"detail": "Predictions can only be submitted for the next gameweek."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkPredictionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_fixture_ids = set(gameweek.matches.values_list("id", flat=True))
        submitted = serializer.validated_data["predictions"]
        submitted_fixture_ids = {item["fixture_id"] for item in submitted}

        invalid_fixture_ids = submitted_fixture_ids - valid_fixture_ids
        if invalid_fixture_ids:
            return Response(
                {"detail": f"Fixture {next(iter(invalid_fixture_ids))} is not part of gameweek {number}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing_fixture_ids = valid_fixture_ids - submitted_fixture_ids
        if missing_fixture_ids:
            return Response(
                {"detail": "A prediction is required for every fixture in this gameweek before saving."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in submitted:
            Prediction.objects.update_or_create(
                user=request.user,
                fixture_id=item["fixture_id"],
                defaults={
                    "predicted_home_score": item["home_score"],
                    "predicted_away_score": item["away_score"],
                },
            )

        return self.get(request, number)


class MyPredictionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        totals = (
            Prediction.objects.filter(user=request.user, fixture__gameweek__is_scored=True)
            .values("fixture__gameweek__number")
            .annotate(points=Sum("points"))
            .order_by("fixture__gameweek__number")
        )
        overall_total = sum(row["points"] or 0 for row in totals)
        return Response(
            {
                "overall_total": overall_total,
                "by_gameweek": [
                    {"gameweek": row["fixture__gameweek__number"], "points": row["points"] or 0}
                    for row in totals
                ],
            }
        )
