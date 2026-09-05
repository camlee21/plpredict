import random
import string

from django.conf import settings
from django.db import models

CODE_CHARS = string.ascii_uppercase + string.digits


def generate_league_code():
    while True:
        code = "".join(random.choices(CODE_CHARS, k=6))
        if not League.objects.filter(code=code).exists():
            return code


class League(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_leagues", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="LeagueMembership", related_name="leagues"
    )

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_league_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeagueMembership(models.Model):
    league = models.ForeignKey(League, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="league_memberships", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("league", "user")

    def __str__(self):
        return f"{self.user} in {self.league}"
