from core.models import Item, SalesRecord, RestockRecord
from django.utils import timezone

def sell_item(item: Item, quantity: int):
    if quantity <= 0:
        return False, "Quantity must be positive."

    if item.quantity < quantity:
        return False, "Not enough stock!"

    # Reduce item quantity
    item.quantity -= quantity
    item.save()

    # Log the sale
    SalesRecord.objects.create(
        item=item,
        quantity_sold=quantity,
        date=timezone.now()
    )

    return True, "Sale recorded successfully."


def restock_item(item: Item, quantity: int):
    if quantity <= 0:
        return False, "Quantity must be positive."

    # Increase stock
    item.quantity += quantity
    item.last_restock_date = timezone.now()
    item.save()

    # Log the restock
    RestockRecord.objects.create(
        item=item,
        quantity_added=quantity,
        date=timezone.now()
    )

    return True, "Item restocked."
