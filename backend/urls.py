from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("backend.accounts.urls")),
    path("api/leagues/", include("backend.leagues.urls")),
    path("api/fixtures/", include("backend.fixtures.urls")),
    path("api/predictions/", include("backend.predictions.urls")),
]
