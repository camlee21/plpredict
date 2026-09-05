from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import GoogleAuthSerializer, LoginSerializer, RegisterSerializer, UserSerializer

User = get_user_model()


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_tokens_for_user(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username_or_email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "No account matches those credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(_tokens_for_user(user))


class GoogleAuthView(APIView):
    """Exchanges a Google 'Sign in with Google' ID token for our own JWTs.

    Used for both registration and login: if no account exists for the
    Google account's email yet, one is created transparently.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not settings.GOOGLE_OAUTH_CLIENT_ID:
            return Response(
                {"detail": "Google sign-in is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            payload = google_id_token.verify_oauth2_token(
                serializer.validated_data["id_token"],
                google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except ValueError:
            return Response({"detail": "Invalid Google token."}, status=status.HTTP_401_UNAUTHORIZED)

        google_sub = payload["sub"]
        email = payload.get("email")
        if not email:
            return Response({"detail": "Google account has no email."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(google_sub=google_sub).first()
        if user is None:
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                user.google_sub = google_sub
                user.save(update_fields=["google_sub"])
            else:
                username = _unique_username_from_email(email)
                user = User.objects.create_user(username=username, email=email)
                user.set_unusable_password()
                user.first_name = payload.get("given_name", "")
                user.last_name = payload.get("family_name", "")
                user.google_sub = google_sub
                user.save()

        return Response(_tokens_for_user(user))


def _unique_username_from_email(email):
    base = email.split("@")[0][:150] or "user"
    username = base
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix += 1
        username = f"{base}{suffix}"[:150]
    return username


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
