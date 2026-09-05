from rest_framework import serializers

from .models import MAX_MEMBERS_CHOICES, League

MAX_MEMBERS_VALUES = [choice[0] for choice in MAX_MEMBERS_CHOICES]


class LeagueSerializer(serializers.ModelSerializer):
    """Full detail, for members only - includes the private join code."""

    owner_username = serializers.CharField(source="owner.username", read_only=True)
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)
    is_full = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = (
            "public_id", "name", "code", "is_public", "max_members",
            "owner_username", "member_count", "is_full", "created_at", "starting_gameweek",
        )
        read_only_fields = fields

    def get_is_full(self, obj):
        return obj.memberships.count() >= obj.max_members


class PublicLeagueSerializer(serializers.ModelSerializer):
    """Browse listing for public leagues - never exposes the join code or
    who created it (that's only revealed once you've opened the league)."""

    member_count = serializers.IntegerField(source="memberships.count", read_only=True)
    is_full = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = (
            "public_id", "name", "max_members",
            "member_count", "is_full", "is_member", "created_at", "starting_gameweek",
        )

    def get_is_full(self, obj):
        return obj.memberships.count() >= obj.max_members

    def get_is_member(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user).exists()


class CreateLeagueSerializer(serializers.ModelSerializer):
    max_members = serializers.ChoiceField(choices=MAX_MEMBERS_VALUES, default=8)

    class Meta:
        model = League
        fields = ("name", "is_public", "max_members")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("League name cannot be blank.")
        return value


class JoinLeagueSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)

    def validate_code(self, value):
        return value.upper()
