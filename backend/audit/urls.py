from django.urls import path

from .views import audit_log_list

app_name = "audit"
urlpatterns = [path("audit/", audit_log_list, name="logs")]
