from django.contrib import admin

from .models import Fixture, Gameweek, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "tla", "external_id")
    search_fields = ("name", "short_name", "tla")


@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = ("number", "deadline", "finalize_after", "is_scored")


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ("gameweek", "home_team", "away_team", "kickoff_time", "status", "home_score", "away_score")
    list_filter = ("gameweek", "status")
