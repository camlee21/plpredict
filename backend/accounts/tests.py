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

    def test_rejects_registering_with_an_email_already_used_for_google_sign_in(self):
        google_user = User.objects.create_user(username="alice", email="alice@gmail.com")
        google_user.google_sub = "google-sub-123"
        google_user.save()
        self.assertFalse(google_user.has_usable_password())

        response = self.client.post(
            reverse("register"),
            {"username": "alice2", "email": "alice@gmail.com", "password": "SuperSecret123"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        # No second account was created, and the Google account is untouched -
        # it still has no password an attacker/confused user could log in with.
        self.assertEqual(User.objects.filter(email__iexact="alice@gmail.com").count(), 1)
        google_user.refresh_from_db()
        self.assertFalse(google_user.has_usable_password())

    def test_register_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(username="alice", email="Alice@Gmail.com")

        response = self.client.post(
            reverse("register"),
            {"username": "bob", "email": "alice@gmail.com", "password": "SuperSecret123"},
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
        # Linking a Google login to an existing account must not clobber the
        # password it already had - it should be able to log in either way.
        self.assertTrue(existing.check_password("SuperSecret123"))

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


class GoogleUsernameGenerationTests(APITestCase):
    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_username_defaults_to_the_part_of_the_email_before_the_at_sign(self, mock_verify):
        mock_verify.return_value = {"sub": "google-sub-mike2", "email": "mike2@gmail.com"}
        self.client.post(reverse("google-auth"), {"id_token": "fake-token"})
        user = User.objects.get(email="mike2@gmail.com")
        self.assertEqual(user.username, "mike2")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_username_is_truncated_to_16_characters(self, mock_verify):
        local_part = "areallylongusernamehere"
        mock_verify.return_value = {"sub": "google-sub-long", "email": f"{local_part}@gmail.com"}
        self.client.post(reverse("google-auth"), {"id_token": "fake-token"})
        user = User.objects.get(email=f"{local_part}@gmail.com")
        self.assertEqual(user.username, local_part[:16])

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_username_strips_characters_not_allowed_in_usernames(self, mock_verify):
        mock_verify.return_value = {"sub": "google-sub-plus", "email": "mike+test@gmail.com"}
        self.client.post(reverse("google-auth"), {"id_token": "fake-token"})
        user = User.objects.get(email="mike+test@gmail.com")
        self.assertEqual(user.username, "miketest")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id")
    @patch("backend.accounts.views.google_id_token.verify_oauth2_token")
    def test_username_collision_gets_a_numeric_suffix(self, mock_verify):
        User.objects.create_user(username="mike2", email="existing@example.com", password="pw12345678")
        mock_verify.return_value = {"sub": "google-sub-mike2b", "email": "mike2@gmail.com"}

        self.client.post(reverse("google-auth"), {"id_token": "fake-token"})

        user = User.objects.get(email="mike2@gmail.com")
        self.assertNotEqual(user.username, "mike2")
        self.assertTrue(user.username.startswith("mike2"))
        self.assertLessEqual(len(user.username), 16)


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="SuperSecret123")
        self.client.force_authenticate(user=self.user)

    def test_can_change_username(self):
        response = self.client.patch(reverse("me"), {"username": "newname"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "newname")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newname")

    def test_changed_username_can_be_used_to_log_in(self):
        self.client.patch(reverse("me"), {"username": "newname"})
        self.client.force_authenticate(user=None)

        response = self.client.post(reverse("login"), {"username_or_email": "newname", "password": "SuperSecret123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rejects_duplicate_username(self):
        User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")
        response = self.client.patch(reverse("me"), {"username": "bob"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_username_with_disallowed_characters(self):
        response = self.client.patch(reverse("me"), {"username": "bad name!"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_username_over_16_characters(self):
        response = self.client.patch(reverse("me"), {"username": "a" * 17})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="OldPassword123")
        self.client.force_authenticate(user=self.user)

    def test_can_change_password(self):
        response = self.client.post(
            reverse("change-password"),
            {"current_password": "OldPassword123", "new_password": "NewPassword456"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword456"))

    def test_rejects_wrong_current_password(self):
        response = self.client.post(
            reverse("change-password"),
            {"current_password": "WrongPassword", "new_password": "NewPassword456"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123"))

    def test_rejects_a_weak_new_password(self):
        response = self.client.post(
            reverse("change-password"),
            {"current_password": "OldPassword123", "new_password": "password"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_google_only_account_cannot_change_a_password_that_does_not_exist(self):
        self.user.set_unusable_password()
        self.user.save()

        response = self.client.post(
            reverse("change-password"),
            {"current_password": "whatever", "new_password": "NewPassword456"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse("change-password"),
            {"current_password": "OldPassword123", "new_password": "NewPassword456"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserAdminTests(APITestCase):
    """The Django admin site (/admin/) is where staff manage users - this
    covers the bulk activate/deactivate actions and that only staff can get in."""

    def setUp(self):
        self.staff = User.objects.create_superuser(username="staffuser", email="staff@example.com", password="AdminPass123")
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="pw12345678")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="pw12345678")

    def test_non_staff_cannot_reach_the_user_admin(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

    def test_staff_can_list_users(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_deactivate_users_action_disables_login(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "deactivate_users", "_selected_action": [str(self.alice.pk), str(self.bob.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertFalse(self.alice.is_active)
        self.assertFalse(self.bob.is_active)

    def test_deactivate_users_action_cannot_deactivate_yourself(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "deactivate_users", "_selected_action": [str(self.staff.pk)]},
            follow=True,
        )
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_activate_users_action_restores_login(self):
        self.alice.is_active = False
        self.alice.save(update_fields=["is_active"])

        self.client.force_login(self.staff)
        self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "activate_users", "_selected_action": [str(self.alice.pk)]},
            follow=True,
        )
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_active)

    def test_deactivated_user_cannot_log_in(self):
        self.alice.is_active = False
        self.alice.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("login"), {"username_or_email": "alice", "password": "pw12345678"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
