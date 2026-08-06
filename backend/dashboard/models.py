from django.db import models

from companies.models import Company


class ProductCategory(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    name = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = "product_categories"


class Product(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    category = models.ForeignKey(ProductCategory, on_delete=models.DO_NOTHING, db_column="category_id")
    name = models.CharField(max_length=200)
    minimum_stock = models.DecimalField(max_digits=16, decimal_places=2)
    is_active = models.BooleanField()
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "products"


class Customer(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    name = models.CharField(max_length=200)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "customers"


class Sale(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    sale_date = models.DateField()
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, db_column="customer_id", null=True)
    payment_method = models.CharField(max_length=30)
    payment_status = models.CharField(max_length=30)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "sales"


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    sale = models.ForeignKey(Sale, on_delete=models.DO_NOTHING, db_column="sale_id", related_name="items")
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, db_column="product_id")
    quantity_packages = models.DecimalField(max_digits=16, decimal_places=2)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        managed = False
        db_table = "sale_items"


class DailyStock(models.Model):
    id = models.UUIDField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    stock_date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, db_column="product_id")
    closing_stock = models.DecimalField(max_digits=16, decimal_places=2)
    minimum_stock = models.DecimalField(max_digits=16, decimal_places=2)
    stockout_flag = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "daily_stocks"
