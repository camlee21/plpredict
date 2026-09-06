from django.db import transaction
from django.db.models import Count, F, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.fixtures.models import Fixture, current_gameweek_number
from backend.predictions.models import Prediction
from backend.predictions.scoring import calculate_points

from .models import League, LeagueMembership
from .serializers import CreateLeagueSerializer, JoinLeagueSerializer, LeagueSerializer, PublicLeagueSerializer


def _rank_by_points(rows):
    """Assigns standard competition ranking (1, 2, =3, =3, 5, ...) to `rows`
    (dicts with a "total_points" key), sorted highest points first."""
    rows = sorted(rows, key=lambda row: row["total_points"], reverse=True)
    rank = 0
    for index, row in enumerate(rows):
        if index == 0 or row["total_points"] != rows[index - 1]["total_points"]:
            rank = index + 1
        row["rank"] = rank
    tied_counts = {}
    for row in rows:
        tied_counts[row["rank"]] = tied_counts.get(row["rank"], 0) + 1
    for row in rows:
        row["rank_display"] = _ordinal(row["rank"]) if tied_counts[row["rank"]] == 1 else f"={_ordinal(row['rank'])}"
    return rows


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _current_gameweek_points(member_ids, gameweek_number):
    """Live points each member has scored so far in the current gameweek's
    finished fixtures. This is provisional: it isn't backed by Prediction.points
    (which stays null until the whole gameweek is officially scored, see
    score_gameweeks), and it resets to 0 once that happens and the gameweek's
    points fold into total_points instead."""
    if gameweek_number is None:
        return {}
    predictions = Prediction.objects.filter(
        user_id__in=member_ids,
        fixture__gameweek__number=gameweek_number,
        fixture__status=Fixture.Status.FINISHED,
        fixture__home_score__isnull=False,
        fixture__away_score__isnull=False,
    ).select_related("fixture")

    points = {}
    for prediction in predictions:
        fixture = prediction.fixture
        earned = calculate_points(
            prediction.predicted_home_score, prediction.predicted_away_score,
            fixture.home_score, fixture.away_score,
        )
        points[prediction.user_id] = points.get(prediction.user_id, 0) + earned
    return points


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
        league = serializer.save(owner=request.user, starting_gameweek=current_gameweek_number())
        LeagueMembership.objects.create(league=league, user=request.user)
        return Response(LeagueSerializer(league).data, status=status.HTTP_201_CREATED)


class PublicLeagueListView(APIView):
    """Browsable listing of public leagues that can be joined without a code.

    Supports ?search=<name substring> and ?filter=recent|vacant (default
    "recent") to narrow the listing down. "vacant" only shows leagues that
    still have room to join.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        leagues = League.objects.filter(is_public=True).annotate(member_total=Count("memberships"))

        search = request.query_params.get("search", "").strip()
        if search:
            leagues = leagues.filter(name__icontains=search)

        filter_by = request.query_params.get("filter", "recent")
        if filter_by == "vacant":
            leagues = leagues.filter(member_total__lt=F("max_members"))
        elif filter_by != "recent":
            return Response(
                {"detail": "filter must be 'recent' or 'vacant'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        current_gameweek = current_gameweek_number()
        current_points = _current_gameweek_points(member_ids, current_gameweek)

        standings = []
        for membership in league.memberships.select_related("user"):
            standings.append(
                {
                    "user_id": membership.user_id,
                    "username": membership.user.username,
                    "total_points": totals.get(membership.user_id, 0),
                    "current_gameweek_points": current_points.get(membership.user_id, 0),
                }
            )
        standings = _rank_by_points(standings)

        return Response(
            {
                **LeagueSerializer(league).data,
                "is_owner": league.owner_id == request.user.id,
                "current_gameweek": current_gameweek,
                "standings": standings,
            }
        )


class LeagueHomeSummaryView(APIView):
    """The current user's rank and points in each league they belong to,
    for the home page's "your position in each league" panel."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        summaries = []
        for league in League.objects.filter(memberships__user=request.user):
            member_ids = list(league.memberships.values_list("user_id", flat=True))
            totals = {
                row["user__id"]: row["total"] or 0
                for row in Prediction.objects.filter(
                    user_id__in=member_ids, fixture__gameweek__is_scored=True
                )
                .values("user__id")
                .annotate(total=Sum("points"))
            }
            standings = _rank_by_points(
                [{"user_id": uid, "total_points": totals.get(uid, 0)} for uid in member_ids]
            )
            mine = next(row for row in standings if row["user_id"] == request.user.id)
            summaries.append(
                {
                    "public_id": league.public_id,
                    "name": league.name,
                    "member_count": len(member_ids),
                    "total_points": mine["total_points"],
                    "rank": mine["rank"],
                    "rank_display": mine["rank_display"],
                }
            )
        return Response(summaries)
