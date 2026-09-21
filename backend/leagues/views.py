from django.db import transaction
from django.db.models import Count, F, Min, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.fixtures.models import Fixture, Gameweek, current_gameweek_number, next_open_gameweek_number
from backend.predictions.models import Prediction
from backend.predictions.scoring import calculate_points
from backend.predictions.serializers import FixtureWithPredictionSerializer

from .models import League, LeagueMembership
from .serializers import CreateLeagueSerializer, JoinLeagueSerializer, LeagueSerializer, PublicLeagueSerializer

MAX_LEAGUES_PER_USER = 10


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


def _scored_points_by_gameweek(member_ids):
    """{user_id: {gameweek number: points}} across officially scored
    gameweeks. Kept per-gameweek rather than pre-totalled because each member
    only counts the gameweeks from their own join onwards."""
    by_user = {}
    rows = (
        Prediction.objects.filter(user_id__in=member_ids, fixture__gameweek__is_scored=True)
        .values("user_id", "fixture__gameweek__number")
        .annotate(total=Sum("points"))
    )
    for row in rows:
        by_user.setdefault(row["user_id"], {})[row["fixture__gameweek__number"]] = row["total"] or 0
    return by_user


def _first_kickoffs(numbers=None):
    """{gameweek number: earliest kickoff}, for deciding which gameweeks have
    actually started."""
    gameweeks = Gameweek.objects.all()
    if numbers is not None:
        gameweeks = gameweeks.filter(number__in=numbers)
    return dict(gameweeks.annotate(first=Min("matches__kickoff_time")).values_list("number", "first"))


def _has_started(first_kickoff):
    return first_kickoff is not None and timezone.now() >= first_kickoff


def _predictions_visible(first_kickoff, is_you):
    """Members can only see each other's predictions once the gameweek has
    kicked off, so nobody can copy a rival's picks. Your own are always
    yours to look at."""
    return is_you or _has_started(first_kickoff)


def _counts_towards(membership, gameweek_number):
    """Whether `gameweek_number` falls within this membership's run in the
    league. A null starting_gameweek predates gameweek tracking and counts
    everything."""
    if gameweek_number is None:
        return False
    return membership.starting_gameweek is None or gameweek_number >= membership.starting_gameweek


def _standings(league):
    """Ranked standings rows for `league`. Each member's points only count
    from the gameweek they joined from, so joining a league never carries
    points earned beforehand into it.

    Rows carry `has_counted_gameweeks`/`current_gameweek_counts` alongside the
    numbers so a member who joined too recently for either to mean anything
    yet can be shown as "-" rather than a misleading 0."""
    memberships = list(league.memberships.select_related("user"))
    member_ids = [membership.user_id for membership in memberships]
    scored_points = _scored_points_by_gameweek(member_ids)
    scored_numbers = set(Gameweek.objects.filter(is_scored=True).values_list("number", flat=True))
    current_gameweek = current_gameweek_number()
    current_points = _current_gameweek_points(member_ids, current_gameweek)
    # Nobody has a score in a gameweek that hasn't kicked off yet, so the
    # column reads "-" for everyone until it has.
    current_started = _has_started(_first_kickoffs([current_gameweek]).get(current_gameweek))

    rows = []
    for membership in memberships:
        mine = scored_points.get(membership.user_id, {})
        counts_current = _counts_towards(membership, current_gameweek)
        rows.append(
            {
                "user_id": membership.user_id,
                "username": membership.user.username,
                "starting_gameweek": membership.starting_gameweek,
                "total_points": sum(
                    points for number, points in mine.items() if _counts_towards(membership, number)
                ),
                # Whether any gameweek has been scored since they joined - not
                # whether they predicted in one, so sitting a gameweek out
                # still counts as a real 0 rather than "no score yet".
                "has_counted_gameweeks": any(
                    _counts_towards(membership, number) for number in scored_numbers
                ),
                "current_gameweek_points": current_points.get(membership.user_id, 0) if counts_current else 0,
                "current_gameweek_counts": counts_current and current_started,
            }
        )
    return _rank_by_points(rows)


def _my_standing(league, user_id):
    """The requesting user's rank/points within `league`, using the same
    standard-competition ranking as the full standings table."""
    return next(row for row in _standings(league) if row["user_id"] == user_id)


def _join_league(user, league):
    """Adds `user` to `league` if there's room, locking the row to avoid a
    race letting the league exceed max_members under concurrent joins."""
    with transaction.atomic():
        locked_league = League.objects.select_for_update().get(pk=league.pk)
        if LeagueMembership.objects.filter(league=locked_league, user=user).exists():
            return Response(LeagueSerializer(locked_league).data)
        if locked_league.memberships.count() >= locked_league.max_members:
            return Response({"detail": "This league is full."}, status=status.HTTP_409_CONFLICT)
        if LeagueMembership.objects.filter(user=user).count() >= MAX_LEAGUES_PER_USER:
            return Response(
                {"detail": f"You can only be in up to {MAX_LEAGUES_PER_USER} leagues at a time."},
                status=status.HTTP_409_CONFLICT,
            )
        LeagueMembership.objects.create(
            league=locked_league, user=user, starting_gameweek=next_open_gameweek_number()
        )
    return Response(LeagueSerializer(locked_league).data)


class LeagueListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        leagues = League.objects.filter(memberships__user=request.user).order_by("-created_at")
        data = []
        for league in leagues:
            mine = _my_standing(league, request.user.id)
            data.append(
                {
                    **LeagueSerializer(league).data,
                    "rank_display": mine["rank_display"],
                    "total_points": mine["total_points"],
                    "has_counted_gameweeks": mine["has_counted_gameweeks"],
                }
            )
        return Response(data)

    def post(self, request):
        if LeagueMembership.objects.filter(user=request.user).count() >= MAX_LEAGUES_PER_USER:
            return Response(
                {"detail": f"You can only be in up to {MAX_LEAGUES_PER_USER} leagues at a time."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = CreateLeagueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        starting_gameweek = next_open_gameweek_number()
        league = serializer.save(owner=request.user, starting_gameweek=starting_gameweek)
        LeagueMembership.objects.create(
            league=league, user=request.user, starting_gameweek=starting_gameweek
        )
        return Response(LeagueSerializer(league).data, status=status.HTTP_201_CREATED)


class PublicLeagueListView(APIView):
    """Browsable listing of public leagues that can be joined without a code.

    A league that's already full is never joinable, so it's excluded here
    unconditionally - if it later frees up a spot (someone leaves) it becomes
    eligible again automatically, since this is computed fresh on every request.

    Supports ?search=<name substring> and ?filter=recent|capacity_desc|capacity_asc
    (default "recent") to narrow/order the listing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        leagues = (
            League.objects.filter(is_public=True)
            .annotate(member_total=Count("memberships"))
            .filter(member_total__lt=F("max_members"))
        )

        search = request.query_params.get("search", "").strip()
        if search:
            leagues = leagues.filter(name__icontains=search)

        filter_by = request.query_params.get("filter", "recent")
        if filter_by == "recent":
            leagues = leagues.order_by("-created_at")
        elif filter_by == "capacity_desc":
            leagues = leagues.order_by("-max_members", "-created_at")
        elif filter_by == "capacity_asc":
            leagues = leagues.order_by("max_members", "-created_at")
        else:
            return Response(
                {"detail": "filter must be 'recent', 'capacity_desc' or 'capacity_asc'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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


class LeaveLeagueView(APIView):
    """Leave a league you're a member of. Owners can't leave their own
    league - there's no ownership transfer or league deletion yet, so
    letting them leave would strand the league without an owner."""

    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        league = get_object_or_404(League, public_id=public_id, memberships__user=request.user)
        if league.owner_id == request.user.id:
            return Response(
                {"detail": "League owners can't leave their own league."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        LeagueMembership.objects.filter(league=league, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeagueDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        league = get_object_or_404(League, public_id=public_id, memberships__user=request.user)

        return Response(
            {
                **LeagueSerializer(league).data,
                "is_owner": league.owner_id == request.user.id,
                "current_gameweek": current_gameweek_number(),
                "standings": _standings(league),
            }
        )


def _get_membership(request, public_id, user_id):
    """The (league, membership) pair for a member of a league the requesting
    user also belongs to. 404s for anyone else, so a league's roster stays
    invisible to non-members."""
    league = get_object_or_404(League, public_id=public_id, memberships__user=request.user)
    membership = get_object_or_404(league.memberships.select_related("user"), user_id=user_id)
    return league, membership


class LeagueMemberDetailView(APIView):
    """One member's gameweek-by-gameweek record within a league, covering the
    gameweeks from their own join onwards - the same span their league total
    is built from."""

    permission_classes = [IsAuthenticated]

    def get(self, request, public_id, user_id):
        league, membership = _get_membership(request, public_id, user_id)
        standing = next(row for row in _standings(league) if row["user_id"] == membership.user_id)
        current_gameweek = current_gameweek_number()
        is_you = membership.user_id == request.user.id

        # Career figures span everything they've ever predicted, not just this
        # league - deliberately a different number from their league total.
        career = _scored_points_by_gameweek([membership.user_id]).get(membership.user_id, {})
        career_points = sum(career.values())
        career_gameweeks = len(career)

        gameweeks = []
        if current_gameweek is not None:
            live_points = _current_gameweek_points([membership.user_id], current_gameweek).get(
                membership.user_id, 0
            )
            predicted_counts = dict(
                Prediction.objects.filter(user_id=membership.user_id)
                .values_list("fixture__gameweek__number")
                .annotate(predicted=Count("id"))
            )
            played = Gameweek.objects.filter(number__lte=current_gameweek).order_by("number")
            first_kickoffs = _first_kickoffs([gameweek.number for gameweek in played])
            for gameweek in played:
                if not _counts_towards(membership, gameweek.number):
                    continue
                gameweeks.append(
                    {
                        "gameweek": gameweek.number,
                        "points": (
                            career.get(gameweek.number, 0)
                            if gameweek.is_scored
                            else live_points
                            if gameweek.number == current_gameweek
                            else 0
                        ),
                        "is_scored": gameweek.is_scored,
                        "has_started": _has_started(first_kickoffs.get(gameweek.number)),
                        "has_predictions": predicted_counts.get(gameweek.number, 0) > 0,
                        "predictions_visible": _predictions_visible(
                            first_kickoffs.get(gameweek.number), is_you
                        ),
                    }
                )

        return Response(
            {
                "league": {"public_id": league.public_id, "name": league.name},
                "user_id": membership.user_id,
                "username": membership.user.username,
                "starting_gameweek": membership.starting_gameweek,
                "is_you": is_you,
                "total_points": standing["total_points"],
                "has_counted_gameweeks": standing["has_counted_gameweeks"],
                "current_gameweek_points": standing["current_gameweek_points"],
                "current_gameweek_counts": standing["current_gameweek_counts"],
                "current_gameweek": current_gameweek,
                "rank_display": standing["rank_display"],
                "career_points": career_points,
                "career_gameweeks": career_gameweeks,
                "average_points": round(career_points / career_gameweeks, 1) if career_gameweeks else None,
                "gameweeks": gameweeks,
            }
        )


class LeagueMemberGameweekView(APIView):
    """One member's actual predictions for a single gameweek of a league,
    reachable only for gameweeks that have locked and that fall within their
    own run in the league."""

    permission_classes = [IsAuthenticated]

    def get(self, request, public_id, user_id, number):
        league, membership = _get_membership(request, public_id, user_id)
        gameweek = get_object_or_404(Gameweek, number=number)
        is_you = membership.user_id == request.user.id

        if not _counts_towards(membership, number):
            return Response(
                {
                    "detail": (
                        f"Gameweek {number} is before {membership.user.username} joined this league."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _predictions_visible(_first_kickoffs([number]).get(number), is_you):
            return Response(
                {"detail": "Predictions stay hidden until this gameweek kicks off."},
                status=status.HTTP_403_FORBIDDEN,
            )

        fixtures = list(gameweek.matches.select_related("home_team", "away_team"))
        predictions = Prediction.objects.filter(user_id=membership.user_id, fixture__gameweek=gameweek)
        serializer = FixtureWithPredictionSerializer(
            fixtures, many=True, context={"predictions_by_fixture": {p.fixture_id: p for p in predictions}}
        )
        scored_points = _scored_points_by_gameweek([membership.user_id]).get(membership.user_id, {})
        return Response(
            {
                "league": {"public_id": league.public_id, "name": league.name},
                "user_id": membership.user_id,
                "username": membership.user.username,
                "is_you": is_you,
                "gameweek": number,
                "deadline": gameweek.deadline,
                "is_scored": gameweek.is_scored,
                "points": (
                    scored_points.get(number, 0)
                    if gameweek.is_scored
                    else _current_gameweek_points([membership.user_id], number).get(membership.user_id, 0)
                ),
                "fixtures": serializer.data,
            }
        )


class LeagueHomeSummaryView(APIView):
    """The current user's rank and points in each league they belong to,
    for the home page's "your position in each league" panel."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        summaries = []
        for league in League.objects.filter(memberships__user=request.user):
            mine = _my_standing(league, request.user.id)
            summaries.append(
                {
                    "public_id": league.public_id,
                    "name": league.name,
                    "member_count": league.memberships.count(),
                    "total_points": mine["total_points"],
                    "has_counted_gameweeks": mine["has_counted_gameweeks"],
                    "rank": mine["rank"],
                    "rank_display": mine["rank_display"],
                }
            )
        return Response(summaries)
