from django.urls import path

from .views import JoinLeagueView, LeagueDetailView, LeagueListCreateView

urlpatterns = [
    path("", LeagueListCreateView.as_view(), name="league-list-create"),
    path("join/", JoinLeagueView.as_view(), name="league-join"),
    path("<int:pk>/", LeagueDetailView.as_view(), name="league-detail"),
]
