from django.urls import path

from . import views

app_name = "decisions"
urlpatterns = [
    path("", views.center, name="center"),
    path("produits/<uuid:product_id>/", views.product_detail, name="product-detail"),
    path("produits/<uuid:product_id>/preparer/", views.prepare_restock, name="prepare"),
]
