from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["role"] = user.role

        # ``super().get_token()`` has already persisted an OutstandingToken row
        # holding the *pre-claims* encoding of this token. Adding claims above
        # changes the encoded string, so the stored copy would never match the
        # token the client actually holds -- breaking every lookup by token
        # string. Re-sync the stored copy with what we are about to hand out.
        OutstandingToken.objects.filter(jti=token.payload["jti"]).update(
            token=str(token)
        )
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "password", "password_confirm", "first_name", "last_name")

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "role", "bio", "avatar", "date_joined")
        read_only_fields = ("id", "email", "role", "date_joined")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "bio", "avatar")


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "role", "is_active", "date_joined")
        read_only_fields = ("id", "email", "date_joined")


class LogoutSerializer(serializers.Serializer):
    """Request body for `POST /api/auth/logout/`."""

    refresh = serializers.CharField()


class DetailSerializer(serializers.Serializer):
    """The `{"detail": ...}` / `{"error": ...}` shape this API returns."""

    detail = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
