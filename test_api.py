from fastapi.testclient import TestClient
import pytest

from app import app
from database import get_db, get_db_connection, init_db

TEST_DB_PATH = "test_clothing_store.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Creates a clean SQLite database before each test and cleans it up afterward."""
    import os

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    init_db(TEST_DB_PATH)

    def override_get_db():
        conn = get_db_connection(TEST_DB_PATH)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)


def test_add_and_filter_products():
    # Add two products
    res1 = client.post(
        "/products",
        json={
            "name": "Slim Fit Jeans",
            "category": "Bottoms",
            "size": "L",
            "price": 60.00,
            "cost_price": 25.00,
            "stock": 20,
            "min_stock_threshold": 5,
        },
    )
    assert res1.status_code == 201
    assert res1.json()["name"] == "Slim Fit Jeans"

    res2 = client.post(
        "/products",
        json={
            "name": "Graphic Tee",
            "category": "Tops",
            "size": "M",
            "price": 25.00,
            "cost_price": 8.00,
            "stock": 15,
            "min_stock_threshold": 5,
        },
    )
    assert res2.status_code == 201

    # Get all products
    all_res = client.get("/products")
    assert all_res.status_code == 200
    assert len(all_res.json()) == 2

    # Filter by category
    cat_res = client.get("/products?category=tops")
    assert cat_res.status_code == 200
    assert len(cat_res.json()) == 1
    assert cat_res.json()[0]["name"] == "Graphic Tee"

    # Filter by size
    size_res = client.get("/products?size=L")
    assert size_res.status_code == 200
    assert len(size_res.json()) == 1
    assert size_res.json()[0]["name"] == "Slim Fit Jeans"


def test_record_sale_and_stock_errors():
    # Create a product with 5 units in stock
    prod_res = client.post(
        "/products",
        json={
            "name": "Wool Sweater",
            "category": "Outerwear",
            "size": "M",
            "price": 80.00,
            "cost_price": 30.00,
            "stock": 5,
            "min_stock_threshold": 3,
        },
    )
    product_id = prod_res.json()["id"]

    # Record a valid sale of 3 units
    sale_res = client.post(
        "/sales",
        json={"product_id": product_id, "quantity": 3},
    )
    assert sale_res.status_code == 201
    sale_data = sale_res.json()
    assert sale_data["total_revenue"] == 240.00  # 3 * 80.00
    assert sale_data["total_profit"] == 150.00   # 3 * (80.00 - 30.00)

    # Verify stock decreased to 2
    products = client.get("/products").json()
    assert products[0]["stock"] == 2

    # Attempt to sell 3 more units (should fail with 400 out-of-stock error)
    fail_res = client.post(
        "/sales",
        json={"product_id": product_id, "quantity": 3},
    )
    assert fail_res.status_code == 400
    assert "Insufficient stock" in fail_res.json()["detail"]

    # Attempt to sell a non-existent product (should fail with 404)
    not_found_res = client.post(
        "/sales",
        json={"product_id": 999, "quantity": 1},
    )
    assert not_found_res.status_code == 404


def test_low_stock_alerts():
    # Product 1: Stock (2) < Threshold (5) -> Should trigger alert
    client.post(
        "/products",
        json={
            "name": "Leather Belt",
            "category": "Accessories",
            "size": "M",
            "price": 35.00,
            "cost_price": 12.00,
            "stock": 2,
            "min_stock_threshold": 5,
        },
    )

    # Product 2: Stock (10) >= Threshold (5) -> Should NOT trigger alert
    client.post(
        "/products",
        json={
            "name": "Denim Jacket",
            "category": "Outerwear",
            "size": "L",
            "price": 90.00,
            "cost_price": 40.00,
            "stock": 10,
            "min_stock_threshold": 5,
        },
    )

    alert_res = client.get("/alerts/low-stock")
    assert alert_res.status_code == 200
    alerts = alert_res.json()
    assert len(alerts) == 1
    assert alerts[0]["name"] == "Leather Belt"


def test_business_analytics():
    # Check analytics when no sales exist
    empty_analytics = client.get("/analytics").json()
    assert empty_analytics["total_revenue"] == 0.0
    assert empty_analytics["total_profit"] == 0.0
    assert empty_analytics["top_selling_products"] == []

    # Add two products
    p1 = client.post(
        "/products",
        json={
            "name": "Polo Shirt",
            "category": "Tops",
            "size": "L",
            "price": 40.00,
            "cost_price": 15.00,
            "stock": 30,
        },
    ).json()

    p2 = client.post(
        "/products",
        json={
            "name": "Chino Pants",
            "category": "Bottoms",
            "size": "M",
            "price": 50.00,
            "cost_price": 20.00,
            "stock": 30,
        },
    ).json()

    # Record sales: 5 Polo Shirts and 2 Chino Pants
    client.post("/sales", json={"product_id": p1["id"], "quantity": 5})
    client.post("/sales", json={"product_id": p2["id"], "quantity": 2})

    analytics = client.get("/analytics").json()
    assert analytics["total_revenue"] == 300.00  # (5*40) + (2*50)
    assert analytics["total_profit"] == 185.00   # (5*25) + (2*30)
    assert analytics["total_sales_count"] == 2
    assert len(analytics["top_selling_products"]) == 2
    assert analytics["top_selling_products"][0]["name"] == "Polo Shirt"
    assert analytics["top_selling_products"][0]["units_sold"] == 5
