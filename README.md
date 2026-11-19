# 👕 Advanced Inventory & Analytics API

A fast, lightweight, and production-ready REST API built with **FastAPI** and **SQLite** for managing clothing store inventory, tracking sales transactions, monitoring low-stock alerts, and generating real-time business analytics.

---

## ✨ Features

* **Inventory Management:** Add new apparel items with sizes, categories, retail prices, and wholesale cost prices.
* **Dynamic Filtering:** Quickly filter products by `category` (e.g., *Tops*, *Bottoms*, *Outerwear*) and `size` (e.g., *S*, *M*, *L*, *XL*).
* **Automated Sales & Stock Control:** Record customer sales with automatic stock deduction, revenue/profit calculation, and built-in out-of-stock protection.
* **Low-Stock Alerts:** Instantly identify items whose stock has dropped below their custom minimum threshold.
* **Business Analytics:** Track cumulative revenue, net profit, total sales count, and top-selling products.
* **Automated Testing:** Full test suite powered by `pytest` using isolated temporary SQLite databases.

---

## 📁 Project Structure

```text
inventory_api/
├── app.py              # FastAPI application, Pydantic schemas, and API endpoints
├── database.py         # SQLite connection management and table initialization
├── test_api.py         # Automated pytest suite covering all endpoints & edge cases
├── requirements.txt    # Python project dependencies
└── README.md           # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
* Python **3.9+** installed on your machine.

### 2. Installation
Navigate to the project directory and install the required packages:

```bash
cd inventory_api
pip install -r requirements.txt
```

### 3. Running the Server
Start the FastAPI development server with auto-reload enabled:

```bash
uvicorn app:app --reload
```

Once the server starts, access the interactive API documentation in your browser:
* **Swagger UI:** [http://127.0.0](http://127.0.0)
* **ReDoc:** [http://127.0.0](http://127.0.0)

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/products` | Add a new clothing item to inventory |
| `GET` | `/products` | List all products (supports `?category=` and `?size=` query params) |
| `POST` | `/sales` | Record a sale, deduct stock, and calculate profit/revenue |
| `GET` | `/alerts/low-stock` | Retrieve products where `stock < min_stock_threshold` |
| `GET` | `/analytics` | View total revenue, profit, sales count, and top-selling items |

---

## 💡 Example Usage (`curl`)

### Add a Product
```bash
curl -X POST "http://127.0.0" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Classic Cotton T-Shirt",
           "category": "Tops",
           "size": "M",
           "price": 29.99,
           "cost_price": 10.50,
           "stock": 25,
           "min_stock_threshold": 5
         }'
```

### Record a Sale
```bash
curl -X POST "http://127.0.0" \
     -H "Content-Type: application/json" \
     -d '{
           "product_id": 1,
           "quantity": 3
         }'
```

### View Business Analytics
```bash
curl -X GET "http://127.0.0"
```

---

## 🧪 Running Automated Tests

Run the full `pytest` suite to verify database transactions, stock validation, alerts, and analytics calculations:

```bash
pytest -v
```

*(Note: Tests automatically create and clean up a temporary `test_clothing_store.db` file so your production data remains untouched.)*

---

## 🗄️ Database Schema

* **`products`**: `id`, `name`, `category`, `size`, `price`, `cost_price`, `stock`, `min_stock_threshold`
* **`sales`**: `id`, `product_id` *(FK)*, `quantity`, `total_revenue`, `total_profit`, `sale_date`
