# 🧾 **Inventory Management System (Django)**

A powerful, full-stack inventory management web application built using **Django**, **Bootstrap**, and **Chart.js**.
This system provides complete control over products, stock levels, restocking, sales analytics, reporting, and PDF export.

---

## 🚀 **Features**

### 🔐 **Authentication**

* User signup, login & logout
* Secure access (inventory only visible after login)

---

### 📦 **Inventory Management**

* Add new items with images, expiration dates, and SKU
* Edit items (inline editing supported)
* Delete items
* Search items by name or SKU
* Filters:
  * In Stock
  * Low Stock
  * Out of Stock

---

### ⚙️ **Advanced Inventory Tools**

* **Instant search (AJAX-like behavior)**
* **In-line editing** — update price, name, quantity directly from the table
* **Sortable table columns**
* **Batch operations**:
  * Batch Delete
  * Batch Restock with popup restock amount
* Auto-update timestamps (last restock date)

---

### 📊 **Dashboard & Analytics**

* Total items count
* Low-stock count
* Out-of-stock count
* Inventory table preview
* Status badges: *In stock*, *Low stock*, *Out of stock*

---

### 📈 **Reports & Analytics**

* Low stock and out-of-stock alerts
* Best-selling items (Top 5)
* Worst-selling items (Bottom 5)
* Restocking patterns
* Recently added items (last 30 days)
* Fast-moving & slow-moving inventory (sales velocity)
* Graphs using **Chart.js** for:
  * Best-selling products
  * Worst-selling products

---

### 📄 **PDF Report Generation**

Automatically generated PDF includes:

* Page numbers
* Colors and styled tables
* Top 5 best-selling products (table + chart)
* Top 5 worst-selling products (table + chart)
* Low stock summary
* Full inventory table (with SKU, stock, price, last restock)

---

### 🎨 **UI**

* Fully responsive using **Bootstrap 5**
* Optional **dark/light theme** toggle stored in database settings
* Clean modern layout with cards, tables, badges, and improved spacing

---

## 🛠️ **Technology Stack**

| Layer         | Technology             |
| ------------- |------------------------|
| Backend       | Django (Python)        |
| Frontend      | HTML, CSS, Bootstrap 5 |
| Charts        | Chart.js, Matplotlib   |
| Database      | SQLite (default)       |
| PDF Generator | ReportLab              |
| Images        | Django ImageField      |

---

## 📥 **Installation & Setup**

### 1️⃣ Clone the repository

```bash
git clone https://github.com/drishya3/The-Inventory-App.git
cd The-Inventory-App
```

### 2️⃣ Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Apply migrations

```bash
python manage.py migrate
```

### 5️⃣ Create a superuser (optional but recommended)

```bash
python manage.py createsuperuser
```

### 6️⃣ Run the development server

```bash
python manage.py runserver
```

### 7️⃣ Access the web app

Open your browser and navigate to:

👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 📂 **Project Structure**

```
core/
│── models.py        # Item, SalesRecord, RestockRecord, AppSettings
│── views.py         # All feature logic
│── urls.py          # Routing
│── forms.py         # Add item form
│── templates/       # HTML templates
```

---
