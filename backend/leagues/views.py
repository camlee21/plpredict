from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.predictions.models import Prediction

from .models import League, LeagueMembership
from .serializers import CreateLeagueSerializer, JoinLeagueSerializer, LeagueSerializer, PublicLeagueSerializer


def _join_league(user, league):
    """Adds `user` to `league` if there's room, locking the row to avoid a
    race letting the league exceed max_members under concurrent joins."""
    with transaction.atomic():
        locked_league = League.objects.select_for_update().get(pk=league.pk)
        if LeagueMembership.objects.filter(league=locked_league, user=user).exists():
            return Response(LeagueSerializer(locked_league).data)
        if locked_league.memberships.count() >= locked_league.max_members:
            return Response({"detail": "This league is full."}, status=status.HTTP_409_CONFLICT)
        LeagueMembership.objects.create(league=locked_league, user=user)
    return Response(LeagueSerializer(locked_league).data)


class LeagueListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        leagues = League.objects.filter(memberships__user=request.user).order_by("-created_at")
        return Response(LeagueSerializer(leagues, many=True).data)

    def post(self, request):
        serializer = CreateLeagueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        league = serializer.save(owner=request.user)
        LeagueMembership.objects.create(league=league, user=request.user)
        return Response(LeagueSerializer(league).data, status=status.HTTP_201_CREATED)


class PublicLeagueListView(APIView):
    """Browsable listing of public leagues that can be joined without a code.

    Supports ?search=<name substring> and ?created_after=/?created_before=
    (YYYY-MM-DD) to narrow the listing down.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        leagues = League.objects.filter(is_public=True)

        search = request.query_params.get("search", "").strip()
        if search:
            leagues = leagues.filter(name__icontains=search)

        for param, lookup in (("created_after", "created_at__date__gte"), ("created_before", "created_at__date__lte")):
            raw_value = request.query_params.get(param)
            if not raw_value:
                continue
            parsed = parse_date(raw_value)
            if parsed is None:
                return Response(
                    {"detail": f"{param} must be a date in YYYY-MM-DD format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            leagues = leagues.filter(**{lookup: parsed})

        leagues = leagues.order_by("-created_at")
        serializer = PublicLeagueSerializer(leagues, many=True, context={"request": request})
        return Response(serializer.data)


class JoinLeagueView(APIView):
    """Join a (typically private) league via its 6-character invite code."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = JoinLeagueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        league = get_object_or_404(League, code=serializer.validated_data["code"])
        return _join_league(request.user, league)


class JoinPublicLeagueView(APIView):
    """Join a public league directly by its public id, no code required."""

    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        league = get_object_or_404(League, public_id=public_id)
        if not league.is_public:
            return Response(
                {"detail": "This league is private; you need an invite code to join."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _join_league(request.user, league)


class LeagueDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        league = get_object_or_404(League, public_id=public_id, memberships__user=request.user)

        member_ids = list(league.memberships.values_list("user_id", flat=True))
        totals = {
            row["user__id"]: row["total"] or 0
            for row in Prediction.objects.filter(
                user_id__in=member_ids, fixture__gameweek__is_scored=True
            )
            .values("user__id")
            .annotate(total=Sum("points"))
        }

        standings = []
        for membership in league.memberships.select_related("user"):
            standings.append(
                {
                    "user_id": membership.user_id,
                    "username": membership.user.username,
                    "total_points": totals.get(membership.user_id, 0),
                }
            )
        standings.sort(key=lambda row: row["total_points"], reverse=True)

        return Response(
            {
                **LeagueSerializer(league).data,
                "is_owner": league.owner_id == request.user.id,
                "standings": standings,
            }
        )
