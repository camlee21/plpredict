from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.predictions.models import Prediction

from .models import League, LeagueMembership
from .serializers import CreateLeagueSerializer, JoinLeagueSerializer, LeagueSerializer


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


class JoinLeagueView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = JoinLeagueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        league = get_object_or_404(League, code=serializer.validated_data["code"])
        LeagueMembership.objects.get_or_create(league=league, user=request.user)
        return Response(LeagueSerializer(league).data)


class LeagueDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        league = get_object_or_404(League, pk=pk, memberships__user=request.user)

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
