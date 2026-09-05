from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    google_sub = models.CharField(
        max_length=255, unique=True, null=True, blank=True,
        help_text="Google's unique subject ID, set when the user signs in via Google OAuth.",
    )

    def __str__(self):
        return self.username
