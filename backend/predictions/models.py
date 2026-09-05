from django.conf import settings
from django.db import models

from backend.fixtures.models import Fixture


class Prediction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="predictions", on_delete=models.CASCADE)
    fixture = models.ForeignKey(Fixture, related_name="predictions", on_delete=models.CASCADE)
    predicted_home_score = models.PositiveSmallIntegerField()
    predicted_away_score = models.PositiveSmallIntegerField()
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "fixture")

    def __str__(self):
        return f"{self.user}: {self.fixture} -> {self.predicted_home_score}-{self.predicted_away_score}"
