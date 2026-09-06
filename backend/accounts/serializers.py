from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .validators import USERNAME_MAX_LENGTH, validate_username_format

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "date_joined", "has_usable_password_flag")

    has_usable_password_flag = serializers.SerializerMethodField()

    def get_has_usable_password_flag(self, obj):
        return obj.has_usable_password()


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate_username(self, value):
        validate_username_format(value)
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class ProfileUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=False)

    class Meta:
        model = User
        fields = ("username",)

    def validate_username(self, value):
        validate_username_format(value)
        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        if not self.instance.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self):
        self.instance.set_password(self.validated_data["new_password"])
        self.instance.save(update_fields=["password"])
        return self.instance


class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()
