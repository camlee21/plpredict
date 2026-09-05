from django.urls import path

from .views import CurrentGameweekView, GameweekDetailView, GameweekListView, HomeGameweekView

urlpatterns = [
    path("gameweeks/", GameweekListView.as_view(), name="gameweek-list"),
    path("gameweeks/current/", CurrentGameweekView.as_view(), name="gameweek-current"),
    path("gameweeks/home/", HomeGameweekView.as_view(), name="gameweek-home"),
    path("gameweeks/<int:number>/", GameweekDetailView.as_view(), name="gameweek-detail"),
]
