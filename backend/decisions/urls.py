from django.urls import path

from . import views

app_name = "decisions"
urlpatterns = [
    path("", views.center, name="center"),
    path("commandes/", views.orders, name="orders"),
    path(
        "commandes/nouvelle/",
        views.manual_order_create,
        name="manual-order-create",
    ),
    path("commandes/creer/", views.create_order, name="create-order"),
    path("commandes/<uuid:order_id>/", views.order_detail, name="order-detail"),
    path("commandes/<uuid:order_id>/bon.pdf", views.order_document, name="order-document"),
    path(
        "commandes/<uuid:order_id>/envoyer/",
        views.send_order,
        name="send-order",
    ),
    path(
        "commandes/<uuid:order_id>/receptionner/",
        views.receive_order,
        name="receive-order",
    ),
    path(
        "commandes/<uuid:order_id>/annuler/",
        views.cancel_order,
        name="cancel-order",
    ),
    path("receptions/", views.receipts, name="receipts"),
    path("produits/<uuid:product_id>/", views.product_detail, name="product-detail"),
    path("produits/<uuid:product_id>/preparer/", views.prepare_restock, name="prepare"),
]
