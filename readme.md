# Django Inventory App

A simple Django web application for managing inventory with features like tracking stock, adding/editing items, and visualizing low/out-of-stock items.

## Features
- Add, edit, and delete inventory items
- Highlight low-stock or out-of-stock items
- Bootstrap-based responsive UI

## Installation
1. Clone the repository:  
   ```bash
   git clone <repo_url>
    ```
2. Install dependencies: 
    ```bash
   pip install -r requirements.txt
    ```
3. Apply migrations:
    ```bash
   python manage.py migrate
    ```
4. Run the development server:
    ```
   python manage.py runserver
   ```
5. Access the website
    ```bash
    http://127.0.0.1:8000/
   ```