"""Tests for idempotent logout behavior in token blacklisting."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

User = get_user_model()


class LogoutIdempotencyTests(TestCase):
    databases = "__all__"
    """Ensure that repeated logout attempts for the same refresh token do not crash."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.login_url = reverse("login")
        self.logout_url = reverse("logout")

    def test_logout_blacklists_token(self):
        """A valid logout should blacklist the refresh token."""
        # Login to get a valid refresh token
        response = self.client.post(
            self.login_url,
            {"email": "test@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 200)
        refresh_token = response.json()["refresh"]

        # Logout should succeed
        self.client.force_authenticate(user=self.user)
        logout_response = self.client.post(
            self.logout_url,
            {"refresh": refresh_token},
        )
        self.assertEqual(logout_response.status_code, 200)

        # Verify token was blacklisted
        self.assertTrue(
            BlacklistedToken.objects.filter(
                token__token=refresh_token
            ).exists()
        )

    def test_logout_is_idempotent(self):
        """Calling logout twice with the same refresh token should succeed both times."""
        # Login to get a valid refresh token
        response = self.client.post(
            self.login_url,
            {"email": "test@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 200)
        refresh_token = response.json()["refresh"]

        # First logout should succeed
        self.client.force_authenticate(user=self.user)
        first_logout = self.client.post(
            self.logout_url,
            {"refresh": refresh_token},
        )
        self.assertEqual(first_logout.status_code, 200)

        # Second logout with same token should also succeed (idempotent)
        second_logout = self.client.post(
            self.logout_url,
            {"refresh": refresh_token},
        )
        self.assertEqual(second_logout.status_code, 200)

        # Token should still be blacklisted
        self.assertTrue(
            BlacklistedToken.objects.filter(
                token__token=refresh_token
            ).exists()
        )

    def test_logout_requires_token(self):
        """Logout without a refresh token should return 400."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.logout_url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_logout_rejects_invalid_token(self):
        """Logout with an invalid refresh token should return 400."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.logout_url,
            {"refresh": "invalid-token-string"},
        )
        self.assertEqual(response.status_code, 400)
