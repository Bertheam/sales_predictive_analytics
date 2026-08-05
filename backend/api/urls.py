from django.urls import path

from .views import (
    CompanyListView,
    ContextView,
    DashboardSummaryView,
    MeView,
    ProductListView,
    SaleListView,
    StockListView,
)

app_name = "api"
urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("companies/", CompanyListView.as_view(), name="companies"),
    path("context/", ContextView.as_view(), name="context"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("products/", ProductListView.as_view(), name="products"),
    path("stocks/", StockListView.as_view(), name="stocks"),
    path("sales/", SaleListView.as_view(), name="sales"),
]
