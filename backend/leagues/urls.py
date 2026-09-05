from django.urls import path

from .views import (
    JoinLeagueView,
    JoinPublicLeagueView,
    LeagueDetailView,
    LeagueListCreateView,
    PublicLeagueListView,
)

urlpatterns = [
    path("", LeagueListCreateView.as_view(), name="league-list-create"),
    path("browse/", PublicLeagueListView.as_view(), name="league-browse"),
    path("join/", JoinLeagueView.as_view(), name="league-join"),
    path("<str:public_id>/", LeagueDetailView.as_view(), name="league-detail"),
    path("<str:public_id>/join/", JoinPublicLeagueView.as_view(), name="league-join-public"),
]
