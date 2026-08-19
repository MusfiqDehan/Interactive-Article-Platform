from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from common.throttles import AuthRateThrottle

from . import views


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = (AuthRateThrottle,)


urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.CustomTokenObtainPairView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", ThrottledTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("users/", views.UserListView.as_view(), name="user-list"),
]
