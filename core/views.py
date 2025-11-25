from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.db import models
from .forms import AddItemForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import now
import json
import calendar
from decimal import Decimal

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, PageBreak
)
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import date, timedelta, datetime

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



@login_required
def home(request):
    return render(request, "home.html")


@login_required()
def dashboard(request):
    items = Item.objects.all()
    settings_obj = AppSettings.objects.first()
    threshold = settings_obj.low_stock_threshold if settings_obj else 10

    # Basic counts
    total_items = items.count()
    out_of_stock_count = items.filter(quantity=0).count()
    low_stock_count = items.filter(quantity__gt=0, quantity__lt=threshold).count()

    # 1) Recent Restocks (use RestockRecord, show last 6)
    recent_restocks_qs = RestockRecord.objects.select_related("item").order_by("-date")[:6]

    # 2) Monthly Restock Risk:
    #    Estimate which items will run low by month end based on last 30 days average sales.
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = date(today.year, today.month, last_day)
    days_left = (month_end - today).days if month_end > today else 0
    lookback_days = 30
    lookback_start = today - timedelta(days=lookback_days)

    # Sales in the last 30 days per item
    recent_sales = (
        SalesRecord.objects.filter(date__gte=lookback_start)
        .values("item")
        .annotate(total_sold=Sum("quantity_sold"))
    )
    # map item_id -> total_sold
    sales_map = {r["item"]: r["total_sold"] for r in recent_sales}

    monthly_risk_items = []
    for it in items:
        sold_last_30 = sales_map.get(it.id, 0)
        avg_daily = sold_last_30 / lookback_days if lookback_days > 0 else 0
        projected_future_sales = avg_daily * days_left
        projected_stock = it.quantity - projected_future_sales
        if projected_stock < threshold:
            monthly_risk_items.append({
                "id": it.id,
                "name": it.name,
                "sku": it.sku,
                "current_qty": it.quantity,
                "projected_stock": max(0, int(projected_stock)),
                "avg_daily": round(avg_daily, 2),
            })

    # 3) Low stock alerts (list few)
    low_stock_qs = items.filter(quantity__gt=0, quantity__lt=threshold).order_by("quantity")[:8]

    # 4) Sales/Usage Trends - small chart data (top 6 items by recent sales)
    sales_velocity = (
        SalesRecord.objects.filter(date__gte=lookback_start)
        .values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("-total_sold")[:6]
    )
    chart_labels = [r["item__name"] for r in sales_velocity]
    chart_values = [r["total_sold"] for r in sales_velocity]

    context = {
        "total_items": total_items,
        "out_of_stock": out_of_stock_count,
        "low_stock": low_stock_count,
        "items": items[:50],  # keep dashboard lightweight - only first 50 for overview
        "recent_restocks": recent_restocks_qs,
        "monthly_risk_items": monthly_risk_items,
        "low_stock_items": low_stock_qs,
        "sales_chart_labels": json.dumps(chart_labels),
        "sales_chart_values": json.dumps(chart_values),
        "low_stock_threshold": threshold,
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

    today = date.today()
    next_month = today + timedelta(days=30)
    # THRESHOLD
    settings = AppSettings.objects.first()
    threshold = settings.low_stock_threshold if settings else 10

    # LOW / OUT OF STOCK
    low_stock = Item.objects.filter(quantity__gt=0, quantity__lt=threshold)
    out_of_stock = Item.objects.filter(quantity=0)

    # BEST / WORST SELLING
    best_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("-total_sold")[:5]
    )

    worst_selling = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("total_sold")[:5]
    )

    # RECENT ITEMS (last 30 days)
    recent_items = Item.objects.filter(created_at__gte=now() - timedelta(days=30))

    # RESTOCK PATTERNS
    restock_patterns = (
        RestockRecord.objects
        .values('item__name')
        .annotate(
            total_restocked=Sum('quantity_added'),
            restock_count=Count('id')
        )
        .order_by('-total_restocked')
    )

    # SALES VELOCITY (last 30 days)
    sales_velocity = (
        SalesRecord.objects
        .filter(date__gte=now() - timedelta(days=30))
        .values('item__name')
        .annotate(
            total_sold=Sum('quantity_sold'),
        )
        .order_by('-total_sold')
    )

    # Expirations
    expired_items = Item.objects.filter(expiration_date__lt=today)
    expiring_soon = Item.objects.filter(
        expiration_date__gte=today,
        expiration_date__lte=next_month
    )
    fast_movers = list(sales_velocity[:5])
    slow_movers = list(sales_velocity.reverse()[:5])

    return render(request, "reports.html", {
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "best_selling": best_selling,
        "worst_selling": worst_selling,
        "recent_items": recent_items,
        "restock_patterns": restock_patterns,
        "fast_movers": fast_movers,
        "slow_movers": slow_movers,
        "expired_items": expired_items,
        "expiring_soon": expiring_soon,
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


# helper: add page numbers with enhanced footer
def _add_page_number(canvas: Canvas, doc):
    page_num = canvas.getPageNumber()
    canvas.saveState()
    # Footer line
    canvas.setStrokeColor(colors.HexColor("#E0E0E0"))
    canvas.setLineWidth(0.5)
    canvas.line(18, 25, letter[0] - 18, 25)
    # Page number
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#757575"))
    canvas.drawRightString(letter[0] - 18, 15, f"Page {page_num}")
    # Report title in footer
    canvas.drawString(18, 15, "Inventory Analytics Report")
    canvas.restoreState()


# helper: create chart image in-memory (BytesIO)
def _make_bar_chart(list_of_pairs, title, color="#1976D2"):
    """
    list_of_pairs: [("Label1", value1), ("Label2", value2), ...]
    returns: BytesIO containing PNG image
    """
    if not list_of_pairs:
        buf = BytesIO()
        plt.figure(figsize=(5, 3))
        plt.text(0.5, 0.5, "No data available", ha="center", va="center",
                 fontsize=12, color="#757575")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf

    labels, values = zip(*list_of_pairs)
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    bars = ax.bar(labels, values, color=color, alpha=0.85, edgecolor='white', linewidth=1.5)

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
    ax.tick_params(axis='x', rotation=30, labelsize=9)
    ax.tick_params(axis='y', labelsize=9)
    ax.set_ylim(bottom=0, top=max(values) * 1.15 if values else 1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


# MAIN view: integrated PDF generator
@login_required
def download_report_pdf(request):
    # SETTINGS & THRESHOLD
    settings_obj = AppSettings.objects.first()
    threshold = settings_obj.low_stock_threshold if settings_obj else 10

    # DATA QUERIES
    low_stock_qs = Item.objects.filter(quantity__gt=0, quantity__lt=threshold)
    out_of_stock_qs = Item.objects.filter(quantity=0)

    best_selling_qs = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("-total_sold")[:5]
    )

    worst_selling_qs = (
        SalesRecord.objects.values("item__name")
        .annotate(total_sold=Sum("quantity_sold"))
        .order_by("total_sold")[:5]
    )

    recent_items_qs = Item.objects.filter(created_at__gte=date.today() - timedelta(days=30))
    all_items_qs = Item.objects.all().order_by("name")

    # Prepare chart data
    best_pairs = [(r["item__name"], r["total_sold"]) for r in best_selling_qs]
    worst_pairs = [(r["item__name"], r["total_sold"]) for r in worst_selling_qs]

    # Generate charts with different colors
    best_chart_buf = _make_bar_chart(best_pairs, "Top 5 Best Selling Products", "#4CAF50")
    worst_chart_buf = _make_bar_chart(worst_pairs, "Top 5 Worst Selling Products", "#F44336")

    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=40, leftMargin=40,
                            topMargin=50, bottomMargin=40)

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=28,
        textColor=colors.HexColor("#1976D2"),
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )

    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor("#424242"),
        spaceAfter=12,
        spaceBefore=8,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor("#1976D2"),
        borderPadding=8,
        leftIndent=0
    )

    info_box_style = ParagraphStyle(
        'InfoBox',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor("#424242"),
        leftIndent=10,
        rightIndent=10
    )

    elements = []

    # Title page with better design
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("📊 Inventory Analytics Report", title_style))
    elements.append(Spacer(1, 30))

    # Info box with report details
    info_data = [
        ["Report Generated:", date.today().strftime('%B %d, %Y')],
        ["Low Stock Threshold:", f"{threshold} units"],
        ["Report Period:", "Last 30 days"]
    ]
    info_table = Table(info_data, colWidths=[140, 200])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E3F2FD")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#424242")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#90CAF9")),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 30))

    # Summary metrics cards
    summary_data = [
        ["Total Items", "Low Stock Items", "Out of Stock"],
        [str(all_items_qs.count()), str(low_stock_qs.count()), str(out_of_stock_qs.count())]
    ]
    summary_table = Table(summary_data, colWidths=[140, 140, 140])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#424242")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#E3F2FD")),
        ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#FFF9C4")),
        ("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#FFCDD2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, 1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, 0), 12),
        ("PADDING", (0, 1), (-1, 1), 20),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#BDBDBD")),
        ("GRID", (0, 0), (-1, -1), 1, colors.white),
    ]))
    elements.append(summary_table)
    elements.append(PageBreak())

    # Low stock section
    elements.append(Paragraph("⚠️ Low Stock Alert", h2_style))
    elements.append(Spacer(1, 10))

    if low_stock_qs.exists():
        low_stock_table = [["Item Name", "SKU", "Qty", "Last Restock"]]
        for it in low_stock_qs:
            low_stock_table.append([it.name, it.sku, str(it.quantity),
                                    str(it.last_restock_date) if it.last_restock_date else "N/A"])
        t = Table(low_stock_table, hAlign="LEFT", repeatRows=1, colWidths=[200, 100, 60, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFA726")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF3E0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FFB74D")),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF3E0"), colors.white]),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("✓ No items currently low on stock", info_box_style))

    elements.append(PageBreak())

    # Best selling section
    elements.append(Paragraph("🏆 Top Performing Products", h2_style))
    elements.append(Spacer(1, 10))

    if best_selling_qs.exists():
        best_table = [["Rank", "Product Name", "Units Sold"]]
        for idx, row in enumerate(best_selling_qs, 1):
            best_table.append([f"#{idx}", row["item__name"], str(row["total_sold"])])
        bt = Table(best_table, hAlign="LEFT", repeatRows=1, colWidths=[50, 280, 100])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#E8F5E9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#81C784")),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#E8F5E9"), colors.white]),
        ]))
        elements.append(bt)
        elements.append(Spacer(1, 15))
        elements.append(Image(best_chart_buf, width=400, height=240))
    else:
        elements.append(Paragraph("No sales data available", info_box_style))

    elements.append(PageBreak())

    # Worst selling section
    elements.append(Paragraph("📉 Underperforming Products", h2_style))
    elements.append(Spacer(1, 10))

    if worst_selling_qs.exists():
        worst_table = [["Rank", "Product Name", "Units Sold"]]
        for idx, row in enumerate(worst_selling_qs, 1):
            worst_table.append([f"#{idx}", row["item__name"], str(row["total_sold"])])
        wt = Table(worst_table, hAlign="LEFT", repeatRows=1, colWidths=[50, 280, 100])
        wt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F44336")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFEBEE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EF5350")),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFEBEE"), colors.white]),
        ]))
        elements.append(wt)
        elements.append(Spacer(1, 15))
        elements.append(Image(worst_chart_buf, width=400, height=240))
    else:
        elements.append(Paragraph("No sales data available", info_box_style))

    elements.append(PageBreak())

    # Recent items section
    elements.append(Paragraph("🆕 Recently Added Items", h2_style))
    elements.append(Spacer(1, 10))

    if recent_items_qs.exists():
        recent_table = [["Name", "SKU", "Qty", "Price", "Added"]]
        for it in recent_items_qs:
            recent_table.append([
                it.name, it.sku, str(it.quantity),
                f"${it.price:.2f}", it.created_at.strftime("%m/%d/%Y")
            ])
        rt = Table(recent_table, hAlign="LEFT", repeatRows=1, colWidths=[180, 80, 50, 70, 80])
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2196F3")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#E3F2FD")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#64B5F6")),
            ("ALIGN", (2, 0), (4, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#E3F2FD"), colors.white]),
        ]))
        elements.append(rt)
    else:
        elements.append(Paragraph("No items added in the last 30 days", info_box_style))

    elements.append(PageBreak())

    # Full inventory section
    elements.append(Paragraph("📦 Complete Inventory", h2_style))
    elements.append(Spacer(1, 10))

    inventory_table = [["Name", "SKU", "Qty", "Price", "Restock"]]
    for it in all_items_qs:
        inventory_table.append([
            it.name, it.sku, str(it.quantity),
            f"${it.price:.2f}",
            str(it.last_restock_date) if it.last_restock_date else "N/A"
        ])
    inv_t = Table(inventory_table, hAlign="LEFT", repeatRows=1, colWidths=[170, 80, 50, 70, 90])
    inv_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#607D8B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90A4AE")),
        ("ALIGN", (2, 0), (3, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ECEFF1"), colors.white]),
    ]))
    elements.append(inv_t)

    # Build PDF with enhanced footer
    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="inventory_report.pdf"'
    response.write(pdf)
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


def serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@login_required
def backup_data(request):
    items = Item.objects.all()
    restocks = RestockRecord.objects.all()
    sales = SalesRecord.objects.all()

    data = {
        "items": [
            {k: serialize_value(v) for k, v in item.__dict__.items() if not k.startswith("_")}
            for item in items
        ],
        "restocks": [
            {k: serialize_value(v) for k, v in r.__dict__.items() if not k.startswith("_")}
            for r in restocks
        ],
        "sales": [
            {k: serialize_value(v) for k, v in s.__dict__.items() if not k.startswith("_")}
            for s in sales
        ],
    }

    response = HttpResponse(json.dumps(data, indent=4), content_type="application/json")
    response["Content-Disposition"] = "attachment; filename=inventory_backup.json"

    return response


def safe_json(value):
    if isinstance(value, Decimal):
        return float(value)   # or str(value)
    return value

@login_required
def restore_data(request):
    if request.method == "POST":
        file = request.FILES.get("backup_file")
        if not file:
            messages.error(request, "No file uploaded.")
            return redirect("settings")

        import json
        from decimal import Decimal

        try:
            data = json.load(file)

            # Clear existing data
            Item.objects.all().delete()
            SalesRecord.objects.all().delete()
            RestockRecord.objects.all().delete()

            # Restore Items
            for item in data.get("items", []):
                Item.objects.create(
                    id=item["id"],
                    name=item["name"],
                    sku=item["sku"],
                    quantity=item["quantity"],
                    price=Decimal(item["price"]),  # Convert from string
                    last_restock_date=item["last_restock_date"],
                    expiration_date=item.get("expiration_date")
                )

            # Restore Sales
            for s in data.get("sales", []):
                SalesRecord.objects.create(
                    id=s["id"],
                    item_id=s["item_id"],
                    quantity_sold=s["quantity_sold"],
                    date=s["date"]
                )

            # Restore Restocks
            for r in data.get("restocks", []):
                RestockRecord.objects.create(
                    id=r["id"],
                    item_id=r["item_id"],
                    quantity_added=r["quantity_added"],
                    date=r["date"]
                )

            messages.success(request, "Backup restored successfully!")
            return redirect("settings")

        except Exception as e:
            messages.error(request, f"Error restoring backup: {e}")
            return redirect("settings")

    return redirect("settings")
