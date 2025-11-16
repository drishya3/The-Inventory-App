from django.contrib import admin
from .models import Item, SalesRecord, RestockRecord, AppSettings

admin.site.register(Item)
admin.site.register(SalesRecord)
admin.site.register(RestockRecord)
admin.site.register(AppSettings)
