from django.db import models


class Team(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=50, blank=True)
    tla = models.CharField(max_length=5, blank=True)
    crest_url = models.URLField(blank=True)

    def __str__(self):
        return self.name


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

    class Meta:
        ordering = ["kickoff_time"]

    def __str__(self):
        return f"GW{self.gameweek.number}: {self.home_team} vs {self.away_team}"

    @property
    def is_finished(self):
        return self.status == self.Status.FINISHED and self.home_score is not None and self.away_score is not None
