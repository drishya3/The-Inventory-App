from django.db import models


# Models
class Item(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="items/", blank=True, null=True)
    last_restock_date = models.DateField(auto_now=True)
    expiration_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

class SalesRecord(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity_sold = models.PositiveIntegerField()
    date = models.DateField(auto_now_add=True)

class RestockRecord(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity_added = models.PositiveIntegerField()
    date = models.DateField(auto_now_add=True)

class AppSettings(models.Model):
    low_stock_threshold = models.PositiveIntegerField(default=10)
    theme = models.CharField(max_length=10, default="light")



