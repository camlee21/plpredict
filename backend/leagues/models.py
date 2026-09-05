import random
import string

from django.conf import settings
from django.db import models

from .validators import validate_no_profanity

CODE_CHARS = string.ascii_uppercase + string.digits

MAX_MEMBERS_CHOICES = [(n, str(n)) for n in (4, 8, 16, 32, 64, 128)]
DEFAULT_MAX_MEMBERS = 8
LEAGUE_NAME_MAX_LENGTH = 32


def generate_league_code():
    while True:
        code = "".join(random.choices(CODE_CHARS, k=6))
        if not League.objects.filter(code=code).exists():
            return code


def generate_public_id():
    while True:
        public_id = "".join(random.choices(CODE_CHARS, k=8))
        if not League.objects.filter(public_id=public_id).exists():
            return public_id


class League(models.Model):
    name = models.CharField(max_length=LEAGUE_NAME_MAX_LENGTH, validators=[validate_no_profanity])
    # Shown in shareable links/URLs. Safe to expose publicly - unlike `code`,
    # it doesn't grant join access on its own.
    public_id = models.CharField(max_length=8, unique=True, editable=False)
    # The invite code private leagues are joined with. Only ever shown to
    # existing members.
    code = models.CharField(max_length=6, unique=True, editable=False)
    is_public = models.BooleanField(
        default=True,
        help_text="Public leagues are listed for anyone to browse and join freely.",
    )
    max_members = models.PositiveSmallIntegerField(choices=MAX_MEMBERS_CHOICES, default=DEFAULT_MAX_MEMBERS)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_leagues", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    # The gameweek that was current/next-up when this league was created, so
    # members have context for what its point totals cover. Null only if no
    # gameweeks had been synced yet at creation time.
    starting_gameweek = models.PositiveSmallIntegerField(null=True, blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="LeagueMembership", related_name="leagues"
    )

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_league_code()
        if not self.public_id:
            self.public_id = generate_public_id()
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
