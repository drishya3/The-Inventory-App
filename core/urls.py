from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),

    path("home/", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/<int:item_id>/delete/", views.delete_item, name="delete_item"),
    path("inventory/add/", views.add_item, name="add_item"),
    path("inventory/<int:item_id>/sell/", views.sell_stock, name="sell_stock"),
    path("inventory/<int:item_id>/restock/", views.restock_stock, name="restock_stock"),
    path("inventory/<int:item_id>/", views.item_detail, name="item_detail"),
    path("reports/", views.reports, name="reports"),
    path("reports/pdf/", views.download_report_pdf, name="download_report_pdf"),
    path("settings/", views.settings_page, name="settings"),
    path("restocks/", views.recent_restocks, name="restocks"),
    path("low-stock/", views.low_stock, name="low_stock"),
    path("sales-usage/", views.sales_usage, name="sales_usage"),
]
