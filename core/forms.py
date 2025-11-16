from django import forms
from .models import Item

class AddItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'sku', 'price', 'quantity', 'image', 'expiration_date']
