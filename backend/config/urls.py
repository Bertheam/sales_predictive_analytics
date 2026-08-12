from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView


def health(request):
    return JsonResponse({"status": "ok", "service": "web"})


urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/favicon.svg", permanent=True),
    ),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("compte/", include("accounts.urls")),
    path("depots/", include("companies.urls")),
    path("api/v1/", include("api.urls")),
    path("administration/", include("audit.urls")),
    path("previsions/", include("forecasting.urls")),
    path("reapprovisionnement/", include("decisions.urls")),
    path("", include("operations.urls")),
    path("", include("dashboard.urls")),
]
