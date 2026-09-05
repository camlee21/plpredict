from django.utils import timezone
from rest_framework import serializers

from .models import Fixture, Gameweek, Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("id", "name", "short_name", "tla", "crest_url")


class FixtureSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer()
    away_team = TeamSerializer()

    class Meta:
        model = Fixture
        fields = (
            "id", "home_team", "away_team", "kickoff_time", "status",
            "home_score", "away_score",
        )


class GameweekSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()
    fixture_count = serializers.IntegerField(source="matches.count", read_only=True)

    class Meta:
        model = Gameweek
        fields = ("number", "deadline", "finalize_after", "is_scored", "is_locked", "fixture_count")

    def get_is_locked(self, obj):
        return obj.deadline is None or timezone.now() >= obj.deadline


class GameweekDetailSerializer(GameweekSerializer):
    fixtures = FixtureSerializer(source="matches", many=True)

    class Meta(GameweekSerializer.Meta):
        fields = GameweekSerializer.Meta.fields + ("fixtures",)
