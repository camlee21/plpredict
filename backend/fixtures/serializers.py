from django.utils import timezone
from rest_framework import serializers

from .models import Fixture, Gameweek, Team, current_gameweek_number, recent_form_by_team


class TeamSerializer(serializers.ModelSerializer):
    form = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "short_name", "tla", "crest_url", "form")

    def get_form(self, obj):
        # Filled in for a whole fixture list at once by FixtureListSerializer.
        form_by_team = self.context.get("form_by_team")
        if form_by_team is not None and obj.id in form_by_team:
            return form_by_team[obj.id]
        return obj.recent_form()


def _as_list(data):
    return list(data.all() if hasattr(data, "all") else data)


class FixtureListSerializer(serializers.ListSerializer):
    """Works out every team's form in one query before serialising a list of
    fixtures, instead of one query per team inside TeamSerializer."""

    def to_representation(self, data):
        fixtures = _as_list(data)
        form_by_team = self.context.setdefault("form_by_team", {})
        team_ids = {f.home_team_id for f in fixtures} | {f.away_team_id for f in fixtures}
        missing = team_ids - form_by_team.keys()
        if missing:
            form_by_team.update(recent_form_by_team(missing))
        return super().to_representation(fixtures)


class FixtureSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer()
    away_team = TeamSerializer()

    class Meta:
        model = Fixture
        fields = (
            "id", "home_team", "away_team", "kickoff_time", "status",
            "home_score", "away_score", "home_goals", "away_goals",
        )
        list_serializer_class = FixtureListSerializer


class GameweekListSerializer(serializers.ListSerializer):
    """Works out the current gameweek once for the whole list - each
    gameweek's lifecycle depends on it, and it's a query of its own."""

    def to_representation(self, data):
        self.context.setdefault("current_gameweek", current_gameweek_number())
        return super().to_representation(data)


class GameweekSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()
    # Where this gameweek sits in the season, for grouping/labelling a full
    # gameweek list (distinct from HomeGameweekView's own "phase", which
    # instead flags whether *that specific* gameweek is being shown because
    # it's live or because it's merely the next upcoming one).
    lifecycle = serializers.SerializerMethodField()
    fixture_count = serializers.SerializerMethodField()

    class Meta:
        model = Gameweek
        fields = ("number", "deadline", "finalize_after", "is_scored", "is_locked", "lifecycle", "fixture_count")
        list_serializer_class = GameweekListSerializer

    def get_is_locked(self, obj):
        return obj.deadline is None or timezone.now() >= obj.deadline

    def get_lifecycle(self, obj):
        if obj.is_scored:
            return "previous"
        if "current_gameweek" in self.context:
            current = self.context["current_gameweek"]
        else:
            current = current_gameweek_number()
        if obj.number == current:
            return "current"
        return "future"

    def get_fixture_count(self, obj):
        # GameweekListView annotates this in the same query as the list.
        annotated = getattr(obj, "fixture_total", None)
        return obj.matches.count() if annotated is None else annotated


class GameweekDetailSerializer(GameweekSerializer):
    fixtures = FixtureSerializer(source="matches", many=True)

    class Meta(GameweekSerializer.Meta):
        fields = GameweekSerializer.Meta.fields + ("fixtures",)
