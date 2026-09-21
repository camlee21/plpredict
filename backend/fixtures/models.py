from django.db import models
from django.utils import timezone

FORM_LENGTH = 5


class Team(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=50, blank=True)
    tla = models.CharField(max_length=5, blank=True)
    crest_url = models.URLField(blank=True)

    def __str__(self):
        return self.name

    def recent_form(self, limit=FORM_LENGTH):
        """The team's last `limit` results as a list of "W"/"D"/"L",
        oldest first, based on finished fixtures up to now."""
        fixtures = (
            Fixture.objects.filter(
                models.Q(home_team=self) | models.Q(away_team=self),
                status=Fixture.Status.FINISHED,
                home_score__isnull=False,
                away_score__isnull=False,
            )
            .order_by("-kickoff_time")[:limit]
        )
        results = []
        for fixture in fixtures:
            if fixture.home_team_id == self.id:
                goals_for, goals_against = fixture.home_score, fixture.away_score
            else:
                goals_for, goals_against = fixture.away_score, fixture.home_score
            if goals_for > goals_against:
                results.append("W")
            elif goals_for < goals_against:
                results.append("L")
            else:
                results.append("D")
        results.reverse()
        return results


class Player(models.Model):
    external_id = models.IntegerField(unique=True)
    team = models.ForeignKey(Team, related_name="players", on_delete=models.CASCADE)
    web_name = models.CharField(max_length=100)

    def __str__(self):
        return self.web_name


class Gameweek(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Predictions lock at this time (1 hour before the first kickoff).",
    )
    finalize_after = models.DateTimeField(
        null=True, blank=True,
        help_text="Scores are safe to finalise after this time (last kickoff + buffer).",
    )
    is_scored = models.BooleanField(default=False)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Gameweek {self.number}"

    def recompute_schedule(self, lock_before, finalize_buffer):
        kickoffs = list(self.matches.values_list("kickoff_time", flat=True))
        if not kickoffs:
            return
        self.deadline = min(kickoffs) - lock_before
        self.finalize_after = max(kickoffs) + finalize_buffer
        self.save(update_fields=["deadline", "finalize_after"])


def _earliest_unscored_gameweek():
    return Gameweek.objects.filter(is_scored=False).order_by("number").first()


def current_gameweek_number():
    """The gameweek number to treat as "now". A gameweek is current from the
    moment the previous one is scored until it is itself scored - i.e. the
    earliest one not yet scored - regardless of whether its own deadline has
    passed. Falls back to the most recent gameweek once the whole season is
    scored. None if no gameweeks have been synced yet."""
    gameweek = _earliest_unscored_gameweek() or Gameweek.objects.order_by("-number").first()
    return gameweek.number if gameweek else None


def next_predictable_gameweek_number():
    """The one gameweek predictions can currently be submitted for: the
    current gameweek (see `current_gameweek_number`), but only while its own
    deadline hasn't passed yet. A gameweek stays "current" after its deadline
    passes (it's in progress, awaiting results) but is no longer predictable.
    None if no gameweek is currently open for predictions."""
    gameweek = _earliest_unscored_gameweek()
    if gameweek is None or gameweek.deadline is None or gameweek.deadline <= timezone.now():
        return None
    return gameweek.number


def next_open_gameweek_number():
    """The earliest gameweek whose predictions haven't locked yet - what a
    new league, or a new member of one, starts counting points from. Once the
    current gameweek's deadline has passed its points are already being
    decided, so a league created then starts from the gameweek after it
    instead. None if no gameweeks have been synced yet."""
    predictable = next_predictable_gameweek_number()
    if predictable is not None:
        return predictable
    current = current_gameweek_number()
    return None if current is None else current + 1


class Fixture(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        LIVE = "LIVE", "Live"
        FINISHED = "FINISHED", "Finished"
        POSTPONED = "POSTPONED", "Postponed"

    external_id = models.IntegerField(unique=True)
    gameweek = models.ForeignKey(Gameweek, related_name="matches", on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, related_name="home_fixtures", on_delete=models.PROTECT)
    away_team = models.ForeignKey(Team, related_name="away_fixtures", on_delete=models.PROTECT)
    kickoff_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    # Each entry: {"player": "<web name>", "count": <goals>, "own_goal": bool}.
    home_goals = models.JSONField(default=list, blank=True)
    away_goals = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["kickoff_time"]

    def __str__(self):
        return f"GW{self.gameweek.number}: {self.home_team} vs {self.away_team}"

    @property
    def is_finished(self):
        return self.status == self.Status.FINISHED and self.home_score is not None and self.away_score is not None
