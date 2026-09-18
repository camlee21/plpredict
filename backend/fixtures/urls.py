from django.urls import path

from .views import (
    CurrentGameweekView,
    GameweekDetailView,
    GameweekListView,
    HomeGameweekView,
    SyncTriggerView,
)

urlpatterns = [
    path("gameweeks/", GameweekListView.as_view(), name="gameweek-list"),
    path("gameweeks/current/", CurrentGameweekView.as_view(), name="gameweek-current"),
    path("gameweeks/home/", HomeGameweekView.as_view(), name="gameweek-home"),
    path("gameweeks/<int:number>/", GameweekDetailView.as_view(), name="gameweek-detail"),
    path("sync/trigger/", SyncTriggerView.as_view(), name="sync-trigger"),
]
