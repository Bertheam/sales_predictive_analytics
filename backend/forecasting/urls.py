from django.urls import path

from . import views

app_name = "forecasting"
urlpatterns = [
    path("", views.forecast_jobs, name="jobs"),
    path("<uuid:job_id>/relancer/", views.retry_forecast_job, name="retry"),
]
