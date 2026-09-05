from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.fixtures.models import Gameweek

from .models import Prediction
from .serializers import BulkPredictionSerializer, FixtureWithPredictionSerializer


class GameweekPredictionsView(APIView):
    """Fetch or submit the current user's predictions for one gameweek."""

    permission_classes = [IsAuthenticated]

    def get(self, request, number):
        gameweek = get_object_or_404(Gameweek, number=number)
        fixtures = list(gameweek.matches.select_related("home_team", "away_team"))
        my_predictions = Prediction.objects.filter(user=request.user, fixture__gameweek=gameweek)
        predictions_by_fixture = {p.fixture_id: p for p in my_predictions}

        serializer = FixtureWithPredictionSerializer(
            fixtures, many=True, context={"predictions_by_fixture": predictions_by_fixture}
        )
        is_locked = gameweek.deadline is None or timezone.now() >= gameweek.deadline
        return Response(
            {
                "gameweek": number,
                "deadline": gameweek.deadline,
                "is_locked": is_locked,
                "is_scored": gameweek.is_scored,
                "fixtures": serializer.data,
            }
        )

    def post(self, request, number):
        gameweek = get_object_or_404(Gameweek, number=number)
        is_locked = gameweek.deadline is None or timezone.now() >= gameweek.deadline
        if is_locked:
            return Response(
                {"detail": "Predictions for this gameweek have locked."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkPredictionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_fixture_ids = set(gameweek.matches.values_list("id", flat=True))
        saved = []
        for item in serializer.validated_data["predictions"]:
            fixture_id = item["fixture_id"]
            if fixture_id not in valid_fixture_ids:
                return Response(
                    {"detail": f"Fixture {fixture_id} is not part of gameweek {number}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            prediction, _ = Prediction.objects.update_or_create(
                user=request.user,
                fixture_id=fixture_id,
                defaults={
                    "predicted_home_score": item["home_score"],
                    "predicted_away_score": item["away_score"],
                },
            )
            saved.append(prediction)

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
