from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db import models
from .forms import AddItemForm
from django.contrib.auth.models import User
from django.contrib import messages
from reportlab.pdfgen import canvas
from django.http import HttpResponse, JsonResponse
import json


from .models import Item, SalesRecord, RestockRecord, AppSettings
from core.services.inventory import sell_item, restock_item


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST["username"],
            password=request.POST["password"]
        )
        if user:
            login(request, user)
            return redirect("dashboard")
        return render(request, "login.html", {"error": True})

    return render(request, "login.html")

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

def signup_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        confirm = request.POST["password2"]

        # password match check
        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "signup.html")

        # username exists check
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, "signup.html")

        # create user
        User.objects.create_user(username=username, password=password)
        messages.success(request, "Account created successfully. Please login.")
        return redirect("login")

    return render(request, "signup.html")


@login_required()
def dashboard(request):
    items = Item.objects.all()

    context = {
        "total_items": items.count(),

        # MUTUALLY EXCLUSIVE:
        "out_of_stock": items.filter(quantity=0).count(),
        "low_stock": items.filter(quantity__gt=0, quantity__lt=10).count(),

        "items": items,
    }

    return render(request, "dashboard.html", context)


@login_required
def inventory_list(request):
    items = Item.objects.all()

    search = request.GET.get("search", "")
    stock_filter = request.GET.get("stock", "")

    if search:
        items = items.filter(
            models.Q(name__icontains=search) |
            models.Q(sku__icontains=search)
        )

    if stock_filter == "low":
        items = items.filter(quantity__gt=0, quantity__lt=10)
    elif stock_filter == "out":
        items = items.filter(quantity=0)
    elif stock_filter == "in":
        items = items.filter(quantity__gte=10)

    return render(request, "inventory_list.html", {"items": items})



@login_required
def add_item(request):
    if request.method == "POST":
        form = AddItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            RestockRecord.objects.create(item=item, quantity_added=item.quantity)
            return redirect("inventory_list")

    form = AddItemForm()
    return render(request, "add_item.html", {"form": form})


@login_required
def item_detail(request, item_id):
    item = Item.objects.get(id=item_id)

    if request.method == "POST":
        item.name = request.POST["name"]
        item.price = request.POST["price"]
        item.quantity = request.POST["quantity"]
        item.save()
        return redirect("inventory_list")

    return render(request, "item_detail.html", {"item": item})

@login_required()
def reports(request):
    settings = AppSettings.objects.first()  # global settings
    threshold = settings.low_stock_threshold if settings else 10

    # MUTUALLY EXCLUSIVE
    low_stock = Item.objects.filter(quantity__gt=0, quantity__lt=threshold)
    out_of_stock = Item.objects.filter(quantity=0)

    # BEST SELLING (Top 5)
    best_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("-total_sold")[:5]
    )

    # WORST SELLING (Bottom 5)
    worst_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("total_sold")[:5]
    )

    context = {
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "best_selling": best_selling,
        "worst_selling": worst_selling,
    }

    return render(request, "reports.html", context)


@login_required
def settings_page(request):
    settings = AppSettings.objects.first() or AppSettings.objects.create()

    if request.method == "POST":
        settings.low_stock_threshold = request.POST.get("threshold")
        settings.theme = request.POST.get("theme")
        settings.save()

        return redirect("settings")

    return render(request, "settings.html", {"settings": settings})



@login_required
def recent_restocks(request):
    restocks = RestockRecord.objects.order_by("-date")
    return render(request, "restocks.html", {"restocks": restocks})


@login_required
def low_stock(request):
    settings = AppSettings.objects.first()
    items = Item.objects.filter(quantity__lt=settings.low_stock_threshold)
    return render(request, "low_stock.html", {"items": items})


@login_required
def sales_usage(request):
    sales = SalesRecord.objects.values("item__name").annotate(total=Sum("quantity_sold"))
    return render(request, "sales_usage.html", {"sales": sales})


@login_required
def sell_stock(request, item_id):
    item = Item.objects.get(id=item_id)

    if request.method == "POST":
        qty = int(request.POST["quantity"])
        success, msg = sell_item(item, qty)

        if success:
            return redirect("inventory_list")
        else:
            return render(request, "sell_stock.html", {"item": item, "error": msg})

    return render(request, "sell_stock.html", {"item": item})


@login_required
def restock_stock(request, item_id):
    item = Item.objects.get(id=item_id)

    if request.method == "POST":
        qty = int(request.POST["quantity"])
        success, msg = restock_item(item, qty)

        if success:
            return redirect("inventory_list")
        else:
            return render(request, "restock_stock.html", {"item": item, "error": msg})

    return render(request, "restock_stock.html", {"item": item})


def download_report_pdf(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="inventory_report.pdf"'

    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 800, "Inventory Report")

    y = 770
    p.setFont("Helvetica", 12)

    # Low Stock
    p.drawString(50, y, "Low Stock Items:")
    y -= 20
    low_stock = Item.objects.filter(quantity__gt=0, quantity__lt=10)
    for item in low_stock:
        p.drawString(70, y, f"{item.name} — {item.quantity}")
        y -= 15

    # Best Selling
    y -= 25
    p.drawString(50, y, "Best Performing Products:")
    y -= 20
    best_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total=Sum("quantity_sold"))
        .order_by("-total")[:5]
    )
    for s in best_selling:
        p.drawString(70, y, f"{s['item__name']} — {s['total']} sold")
        y -= 15

    # Worst Selling
    y -= 25
    p.drawString(50, y, "Worst Performing Products:")
    y -= 20
    worst_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total=Sum("quantity_sold"))
        .order_by("total")[:5]
    )
    for w in worst_selling:
        p.drawString(70, y, f"{w['item__name']} — {w['total']} sold")
        y -= 15

    p.showPage()
    p.save()
    return response


def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    if request.method == "POST":  # Confirm delete
        item.delete()
        return redirect("dashboard")

    # Optional confirmation page (if needed)
    return render(request, "confirm_delete.html", {"item": item})

@login_required
def update_inline(request, item_id):
    data = json.loads(request.body)
    item = Item.objects.get(id=item_id)

    field = data["field"]
    value = data["value"]

    setattr(item, field, value)
    item.save()

    return JsonResponse({"status": "ok"})


@login_required
def batch_delete(request):
    data = json.loads(request.body)
    ids = data["ids"]
    Item.objects.filter(id__in=ids).delete()
    return JsonResponse({"status": "ok"})


@login_required
def batch_restock(request):
    data = json.loads(request.body)
    ids = data["ids"]
    amount = int(data["amount"])

    for item in Item.objects.filter(id__in=ids):
        item.quantity += amount
        item.save()
        RestockRecord.objects.create(item=item, quantity_added=amount)

    return JsonResponse({"status": "ok"})

