from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .forms import AddItemForm
from django.contrib.auth.models import User
from django.contrib import messages

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
            return redirect("home")
        return render(request, "login.html", {"error": True})

    return render(request, "login.html")

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



@login_required
def home(request):
    return render(request, "home.html")

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
    query = request.GET.get("search", "")
    items = Item.objects.filter(name__icontains=query)
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


@login_required
def reports(request):
    low_stock = Item.objects.filter(quantity__lt=10)
    best_selling = SalesRecord.objects.values("item__name").annotate(total=Sum("quantity_sold")).order_by("-total")

    return render(request, "reports.html", {
        "low_stock": low_stock,
        "best_selling": best_selling,
    })


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

