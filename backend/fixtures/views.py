import hmac

from django.conf import settings
from django.core.management import call_command
from django.db.models import Max, Min
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Gameweek, current_gameweek_number
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
        number = current_gameweek_number()
        if number is None:
            return Response({"detail": "No gameweeks have been synced yet."}, status=404)
        return Response(GameweekSerializer(Gameweek.objects.get(number=number)).data)


class HomeGameweekView(APIView):
    """The gameweek to show on the home page: the one currently being played
    (from its first kickoff to its finalize time), or otherwise the next
    upcoming one, falling back to the most recent one once the season ends."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        gameweeks = Gameweek.objects.annotate(
            first_kickoff=Min("matches__kickoff_time"), last_kickoff=Max("matches__kickoff_time")
        ).prefetch_related("matches__home_team", "matches__away_team")

        gameweek = gameweeks.filter(first_kickoff__lte=now, finalize_after__gte=now).order_by("number").first()
        phase = "current"
        if gameweek is None:
            gameweek = gameweeks.filter(first_kickoff__gt=now).order_by("first_kickoff").first()
            phase = "upcoming"
        if gameweek is None:
            gameweek = gameweeks.order_by("-number").first()
            phase = "current"

        if gameweek is None:
            return Response({"detail": "No gameweeks have been synced yet."}, status=404)
        return Response({"phase": phase, **GameweekDetailSerializer(gameweek).data})


class SyncTriggerView(APIView):
    """Pulls the latest fixtures/results and finalises any completed
    gameweek - the production equivalent of the local-dev auto-sync thread
    in backend/fixtures/apps.py. Meant to be hit every few minutes by a free
    external scheduler (e.g. cron-job.org) rather than a paid Render Cron
    Job. Requires the `X-Sync-Secret` header to match SYNC_TRIGGER_SECRET;
    returns 404 (not 403) on any mismatch so the endpoint doesn't advertise
    its own existence to anyone probing without the secret."""

    permission_classes = [AllowAny]

    def post(self, request):
        secret = settings.SYNC_TRIGGER_SECRET
        provided = request.headers.get("X-Sync-Secret", "")
        if not secret or not hmac.compare_digest(secret, provided):
            return Response(status=status.HTTP_404_NOT_FOUND)

        call_command("sync_fixtures")
        call_command("score_gameweeks")
        return Response({"detail": "Synced."})
