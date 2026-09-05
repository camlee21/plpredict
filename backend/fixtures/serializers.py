from django.utils import timezone
from rest_framework import serializers

from .models import Fixture, Gameweek, Team, current_gameweek_number


class TeamSerializer(serializers.ModelSerializer):
    form = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "short_name", "tla", "crest_url", "form")

    def get_form(self, obj):
        return obj.recent_form()


class FixtureSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer()
    away_team = TeamSerializer()

    class Meta:
        model = Fixture
        fields = (
            "id", "home_team", "away_team", "kickoff_time", "status",
            "home_score", "away_score", "home_goals", "away_goals",
        )


class GameweekSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()
    # Where this gameweek sits in the season, for grouping/labelling a full
    # gameweek list (distinct from HomeGameweekView's own "phase", which
    # instead flags whether *that specific* gameweek is being shown because
    # it's live or because it's merely the next upcoming one).
    lifecycle = serializers.SerializerMethodField()
    fixture_count = serializers.IntegerField(source="matches.count", read_only=True)

    class Meta:
        model = Gameweek
        fields = ("number", "deadline", "finalize_after", "is_scored", "is_locked", "lifecycle", "fixture_count")

    def get_is_locked(self, obj):
        return obj.deadline is None or timezone.now() >= obj.deadline

    def get_lifecycle(self, obj):
        if obj.is_scored:
            return "previous"
        if obj.number == current_gameweek_number():
            return "current"
        return "future"


class GameweekDetailSerializer(GameweekSerializer):
    fixtures = FixtureSerializer(source="matches", many=True)

    class Meta(GameweekSerializer.Meta):
        fields = GameweekSerializer.Meta.fields + ("fixtures",)
