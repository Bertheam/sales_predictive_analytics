from django.urls import path

from . import views

app_name = "operations"
urlpatterns = [
    path("produits/", views.products, name="products"),
    path("produits/nouveau/", views.product_create, name="product-create"),
    path("produits/<uuid:product_id>/modifier/", views.product_edit, name="product-edit"),
    path("produits/<uuid:product_id>/archiver/", views.product_archive, name="product-archive"),
    path("clients/", views.customers, name="customers"),
    path("clients/nouveau/", views.customer_create, name="customer-create"),
    path("clients/<uuid:customer_id>/modifier/", views.customer_edit, name="customer-edit"),
    path("clients/<uuid:customer_id>/archiver/", views.customer_archive, name="customer-archive"),
    path("fournisseurs/", views.suppliers, name="suppliers"),
    path("fournisseurs/nouveau/", views.supplier_create, name="supplier-create"),
    path("fournisseurs/<uuid:supplier_id>/modifier/", views.supplier_edit, name="supplier-edit"),
    path("fournisseurs/<uuid:supplier_id>/archiver/", views.supplier_archive, name="supplier-archive"),
    path("stocks/", views.stocks, name="stocks"),
    path("stocks/reception/nouvelle/", views.receipt_create, name="receipt-create"),
    path("stocks/reception/<uuid:receipt_id>/modifier/", views.receipt_edit, name="receipt-edit"),
    path("stocks/reception/<uuid:receipt_id>/annuler/", views.receipt_cancel, name="receipt-cancel"),
    path("stocks/mouvement/nouveau/", views.movement_create, name="movement-create"),
    path("ventes/", views.sales, name="sales"),
    path("ventes/nouvelle/", views.sale_create, name="sale-create"),
    path("ventes/<uuid:sale_id>/", views.sale_show, name="sale-detail"),
    path("ventes/<uuid:sale_id>/modifier/", views.sale_edit, name="sale-edit"),
    path("ventes/<uuid:sale_id>/annuler/", views.sale_cancel, name="sale-cancel"),
]
