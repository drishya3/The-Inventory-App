from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/<int:item_id>/delete/", views.delete_item, name="delete_item"),
    path("inventory/add/", views.add_item, name="add_item"),
    path("inventory/<int:item_id>/sell/", views.sell_stock, name="sell_stock"),
    path("inventory/<int:item_id>/restock/", views.restock_stock, name="restock_stock"),
    path("inventory/<int:item_id>/", views.item_detail, name="item_detail"),
    path("inventory/batch-delete/", views.batch_delete, name="batch_delete"),
    path("inventory/batch-restock/", views.batch_restock, name="batch_restock"),
    path("inventory/<int:item_id>/update-inline/", views.update_inline, name="update_inline"),
    path("reports/", views.reports, name="reports"),
    path("reports/pdf/", views.download_report_pdf, name="download_report_pdf"),
    path("settings/", views.settings_page, name="settings"),
    path("settings/backup/", views.backup_data, name="backup_data"),
    path("settings/restore/", views.restore_data, name="restore_data"),
    path("restocks/", views.recent_restocks, name="restocks"),
    path("low-stock/", views.low_stock, name="low_stock"),
    path("sales-usage/", views.sales_usage, name="sales_usage"),
]