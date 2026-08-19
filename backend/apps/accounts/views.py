from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.permissions import IsAdminUser
from common.throttles import AuthRateThrottle
from common.views import BaseAPIView

from .serializers import (
    CustomTokenObtainPairSerializer,
    DetailSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserListSerializer,
    UserSerializer,
)

User = get_user_model()


@extend_schema(tags=["Auth"])
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = (AuthRateThrottle,)


@extend_schema(tags=["Auth"])
class RegisterView(BaseAPIView):
    """POST /api/auth/register/"""

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (AuthRateThrottle,)
    serializer_class = RegisterSerializer
    pagination_class = None

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Auth"],
    request=LogoutSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # NOTE: deliberately *not* ``RefreshToken(refresh_token)``. That runs the
        # blacklist check during construction and raises TokenError for a token
        # that is already blacklisted -- which would make a second logout fail
        # with 400 and defeat the idempotency this endpoint promises. Decoding
        # through the backend still verifies the signature and expiry, but leaves
        # the "already blacklisted" case for us to treat as success below.
        try:
            payload = token_backend.decode(refresh_token, verify=True)
        except (TokenBackendError, TokenError):
            return Response(
                {"error": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        jti = payload.get("jti")
        if not jti:
            return Response(
                {"error": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outstanding_token = OutstandingToken.objects.get(jti=jti)
        except OutstandingToken.DoesNotExist:
            return Response(
                {"error": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        BlacklistedToken.objects.get_or_create(token=outstanding_token)

        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class ProfileView(BaseAPIView):
    """GET · PUT · PATCH /api/auth/profile/ -- always the caller's own record."""

    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return UserSerializer

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, *, partial):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=partial, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(tags=["Auth"])
class UserListView(BaseAPIView):
    """GET /api/auth/users/"""

    serializer_class = UserListSerializer
    permission_classes = (IsAdminUser,)
    filterset_fields = ("role", "is_active")
    search_fields = ("email", "username", "first_name", "last_name")

    def get_queryset(self):
        # Users are global, not tenant-scoped: per-site access is expressed by
        # SiteMembership rather than by which rows exist.
        return User.objects.all().order_by("-date_joined", "-id")

    def get(self, request):
        return self.list_response(self.get_queryset())
