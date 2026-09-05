from rest_framework import serializers

from .models import League


class LeagueSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    class Meta:
        model = League
        fields = ("id", "name", "code", "owner_username", "member_count", "created_at")
        read_only_fields = ("code", "owner_username", "member_count", "created_at")


class CreateLeagueSerializer(serializers.ModelSerializer):
    class Meta:
        model = League
        fields = ("name",)


class JoinLeagueSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)

    def validate_code(self, value):
        return value.upper()


class StandingRowSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    total_points = serializers.IntegerField()
