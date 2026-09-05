from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Gameweek
from .serializers import GameweekDetailSerializer, GameweekSerializer


class GameweekListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GameweekSerializer
    queryset = Gameweek.objects.all()


class GameweekDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GameweekDetailSerializer
    queryset = Gameweek.objects.prefetch_related("matches__home_team", "matches__away_team")
    lookup_field = "number"


class CurrentGameweekView(APIView):
    """The next gameweek that hasn't locked yet, falling back to the most recent one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        gameweek = (
            Gameweek.objects.filter(deadline__gt=now).order_by("deadline").first()
            or Gameweek.objects.order_by("-number").first()
        )
        if gameweek is None:
            return Response({"detail": "No gameweeks have been synced yet."}, status=404)
        return Response(GameweekSerializer(gameweek).data)
