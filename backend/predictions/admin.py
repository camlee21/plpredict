from django.contrib import admin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("user", "fixture", "predicted_home_score", "predicted_away_score", "points")
    list_filter = ("fixture__gameweek",)
    search_fields = ("user__username", "user__email")
