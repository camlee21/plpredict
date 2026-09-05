from django.urls import path

from .views import GameweekPredictionsView, MyPredictionHistoryView

urlpatterns = [
    path("gameweek/<int:number>/", GameweekPredictionsView.as_view(), name="gameweek-predictions"),
    path("history/", MyPredictionHistoryView.as_view(), name="prediction-history"),
]
