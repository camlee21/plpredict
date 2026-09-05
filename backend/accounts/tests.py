from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RegisterTests(APITestCase):
    def test_register_creates_user_and_returns_tokens(self):
        response = self.client.post(
            reverse("register"),
            {"username": "alice", "email": "alice@example.com", "password": "SuperSecret123"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertTrue(User.objects.get(username="alice").check_password("SuperSecret123"))

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username="alice", email="first@example.com", password="SuperSecret123")

        response = self.client.post(
            reverse("register"),
            {"username": "alice", "email": "second@example.com", "password": "SuperSecret123"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="alice", email="dupe@example.com", password="SuperSecret123")

        response = self.client.post(
            reverse("register"),
            {"username": "bob", "email": "dupe@example.com", "password": "SuperSecret123"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse("register"),
            {"username": "alice", "email": "alice@example.com", "password": "password"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="SuperSecret123"
        )

    def test_login_with_username(self):
        response = self.client.post(
            reverse("login"), {"username_or_email": "alice", "password": "SuperSecret123"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_login_with_email(self):
        response = self.client.post(
            reverse("login"), {"username_or_email": "alice@example.com", "password": "SuperSecret123"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_with_email_is_case_insensitive(self):
        response = self.client.post(
            reverse("login"), {"username_or_email": "ALICE@EXAMPLE.COM", "password": "SuperSecret123"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("login"), {"username_or_email": "alice", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rejects_unknown_user(self):
        response = self.client.post(
            reverse("login"), {"username_or_email": "nobody", "password": "SuperSecret123"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeViewTests(APITestCase):
    def test_me_requires_authentication(self):
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        user = User.objects.create_user(username="alice", email="alice@example.com", password="SuperSecret123")
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alice")
        self.assertEqual(response.data["email"], "alice@example.com")


class GoogleAuthTests(APITestCase):
    def test_google_auth_without_client_id_configured_returns_503(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=""):
            response = self.client.post(reverse("google-auth"), {"id_token": "whatever"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_google_auth_creates_new_user(self, mock_verify):
        mock_verify.return_value = {
            "sub": "google-sub-123",
            "email": "newperson@example.com",
            "given_name": "New",
            "family_name": "Person",
        }

        response = self.client.post(reverse("google-auth"), {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        user = User.objects.get(email="newperson@example.com")
        self.assertEqual(user.google_sub, "google-sub-123")
        self.assertFalse(user.has_usable_password())

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_google_auth_links_existing_account_by_email(self, mock_verify):
        existing = User.objects.create_user(
            username="alice", email="alice@example.com", password="SuperSecret123"
        )
        mock_verify.return_value = {"sub": "google-sub-456", "email": "alice@example.com"}

        response = self.client.post(reverse("google-auth"), {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        existing.refresh_from_db()
        self.assertEqual(existing.google_sub, "google-sub-456")
        self.assertEqual(User.objects.filter(email="alice@example.com").count(), 1)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_google_auth_reuses_account_by_google_sub_on_repeat_login(self, mock_verify):
        mock_verify.return_value = {"sub": "google-sub-789", "email": "person@example.com"}
        self.client.post(reverse("google-auth"), {"id_token": "fake-token"})

        response = self.client.post(reverse("google-auth"), {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email="person@example.com").count(), 1)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_google_auth_rejects_invalid_token(self, mock_verify):
        mock_verify.side_effect = ValueError("bad token")

        response = self.client.post(reverse("google-auth"), {"id_token": "garbage"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
