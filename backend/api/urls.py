from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CompanyListView, ContextView, DashboardSummaryView, ForecastJobDetailView,
    ForecastJobListView, ForecastJobResultView, ForecastJobRetryView, LoginView,
    LogoutView, MeView, MovementListView, ProductListView,
    PurchaseOrderActionView, PurchaseOrderDetailView, PurchaseOrderListView,
    PurchaseOrderReceiptListView, PurchaseOrderReceiveView, ReceiptDetailView,
    ReceiptListView, SaleDetailView, SaleListView, SaleReceiptView, StockListView,
)

app_name = "api"
urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("companies/", CompanyListView.as_view(), name="companies"),
    path("context/", ContextView.as_view(), name="context"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("products/", ProductListView.as_view(), name="products"),
    path("stocks/", StockListView.as_view(), name="stocks"),
    path("stock-movements/", MovementListView.as_view(), name="stock-movements"),
    path("sales/", SaleListView.as_view(), name="sales"),
    path("sales/<uuid:sale_id>/", SaleDetailView.as_view(), name="sale-detail"),
    path("sales/<uuid:sale_id>/receipt/", SaleReceiptView.as_view(), name="sale-receipt"),
    path("receipts/", ReceiptListView.as_view(), name="receipts"),
    path("receipts/<uuid:receipt_id>/", ReceiptDetailView.as_view(), name="receipt-detail"),
    path("purchase-orders/", PurchaseOrderListView.as_view(), name="purchase-orders"),
    path("purchase-orders/<uuid:order_id>/", PurchaseOrderDetailView.as_view(), name="purchase-order-detail"),
    path("purchase-orders/<uuid:order_id>/<str:action>/", PurchaseOrderActionView.as_view(), name="purchase-order-action"),
    path("purchase-orders/<uuid:order_id>/receive/", PurchaseOrderReceiveView.as_view(), name="purchase-order-receive"),
    path("purchase-order-receipts/", PurchaseOrderReceiptListView.as_view(), name="purchase-order-receipts"),
    path("forecast-jobs/", ForecastJobListView.as_view(), name="forecast-jobs"),
    path("forecast-jobs/<uuid:job_id>/", ForecastJobDetailView.as_view(), name="forecast-job-detail"),
    path("forecast-jobs/<uuid:job_id>/result/", ForecastJobResultView.as_view(), name="forecast-job-result"),
    path("forecast-jobs/<uuid:job_id>/retry/", ForecastJobRetryView.as_view(), name="forecast-job-retry"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
