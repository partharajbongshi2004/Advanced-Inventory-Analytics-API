from contextlib import asynccontextmanager
from datetime import datetime, timezone
import sqlite3
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from database import get_db, init_db


# --- Lifespan Event (Initializes DB on startup) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Advanced Inventory & Analytics API",
    description="Inventory management, sales tracking, and business analytics for a clothing store.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Pydantic Schemas ---
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, examples=["Classic Cotton T-Shirt"])
    category: str = Field(..., min_length=1, examples=["Tops"])
    size: str = Field(..., min_length=1, examples=["M"])
    price: float = Field(..., gt=0, examples=[29.99])
    cost_price: float = Field(..., ge=0, examples=[10.50])
    stock: int = Field(..., ge=0, examples=[50])
    min_stock_threshold: int = Field(default=5, ge=0, examples=[10])


class ProductResponse(ProductCreate):
    id: int


class SaleCreate(BaseModel):
    product_id: int = Field(..., gt=0, examples=[1])
    quantity: int = Field(..., gt=0, examples=[2])


class SaleResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    total_revenue: float
    total_profit: float
    sale_date: str


class TopProduct(BaseModel):
    product_id: int
    name: str
    category: str
    size: str
    units_sold: int
    revenue_generated: float


class AnalyticsResponse(BaseModel):
    total_revenue: float
    total_profit: float
    total_sales_count: int
    top_selling_products: List[TopProduct]


# --- Endpoints ---


@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Inventory"],
)
def add_product(
    product: ProductCreate, db: sqlite3.Connection = Depends(get_db)
):
    """Add a new clothing product to the inventory."""
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO products (name, category, size, price, cost_price, stock, min_stock_threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product.name.strip(),
            product.category.strip(),
            product.size.strip().upper(),
            round(product.price, 2),
            round(product.cost_price, 2),
            product.stock,
            product.min_stock_threshold,
        ),
    )
    db.commit()
    product_id = cursor.lastrowid

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    new_product = cursor.fetchone()
    return dict(new_product)


@app.get(
    "/products",
    response_model=List[ProductResponse],
    tags=["Inventory"],
)
def get_products(
    category: Optional[str] = Query(None, description="Filter by category (e.g., Tops, Jeans)"),
    size: Optional[str] = Query(None, description="Filter by size (e.g., S, M, L, XL)"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve all products, optionally filtered by category and/or size."""
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category.strip())

    if size:
        query += " AND UPPER(size) = UPPER(?)"
        params.append(size.strip())

    cursor = db.cursor()
    cursor.execute(query, params)
    products = cursor.fetchall()
    return [dict(row) for row in products]


@app.post(
    "/sales",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sales"],
)
def record_sale(sale: SaleCreate, db: sqlite3.Connection = Depends(get_db)):
    """Record a product sale, deduct stock, and calculate revenue and profit."""
    cursor = db.cursor()

    # Fetch product details
    cursor.execute("SELECT * FROM products WHERE id = ?", (sale.product_id,))
    product = cursor.fetchone()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {sale.product_id} not found.",
        )

    # Check stock availability
    if product["stock"] < sale.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock for '{product['name']}' (Size: {product['size']}). "
                f"Requested: {sale.quantity}, Available: {product['stock']}."
            ),
        )

    # Calculate financials
    total_revenue = round(product["price"] * sale.quantity, 2)
    total_profit = round((product["price"] - product["cost_price"]) * sale.quantity, 2)
    sale_date = datetime.now(timezone.utc).isoformat()
    new_stock = product["stock"] - sale.quantity

    try:
        # Deduct stock
        cursor.execute(
            "UPDATE products SET stock = ? WHERE id = ?",
            (new_stock, sale.product_id),
        )

        # Insert sale record
        cursor.execute(
            """
            INSERT INTO sales (product_id, quantity, total_revenue, total_profit, sale_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sale.product_id, sale.quantity, total_revenue, total_profit, sale_date),
        )
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(e)}",
        )

    sale_id = cursor.lastrowid
    cursor.execute("SELECT * FROM sales WHERE id = ?", (sale_id,))
    recorded_sale = cursor.fetchone()
    return dict(recorded_sale)


@app.get(
    "/alerts/low-stock",
    response_model=List[ProductResponse],
    tags=["Inventory"],
)
def get_low_stock_alerts(db: sqlite3.Connection = Depends(get_db)):
    """Get all products whose current stock is strictly below their min_stock_threshold."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT * FROM products
        WHERE stock < min_stock_threshold
        ORDER BY stock ASC
        """
    )
    low_stock_items = cursor.fetchall()
    return [dict(row) for row in low_stock_items]


@app.get(
    "/analytics",
    response_model=AnalyticsResponse,
    tags=["Analytics"],
)
def get_business_analytics(
    top_n: int = Query(5, ge=1, le=50, description="Number of top-selling products to return"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve overall revenue, profit, and top-selling products."""
    cursor = db.cursor()

    # Aggregate total revenue, profit, and transaction count
    cursor.execute(
        """
        SELECT
            COALESCE(SUM(total_revenue), 0.0) AS total_revenue,
            COALESCE(SUM(total_profit), 0.0) AS total_profit,
            COUNT(id) AS total_sales_count
        FROM sales
        """
    )
    totals = cursor.fetchone()

    # Query top-selling products by units sold
    cursor.execute(
        """
        SELECT
            p.id AS product_id,
            p.name,
            p.category,
            p.size,
            SUM(s.quantity) AS units_sold,
            ROUND(SUM(s.total_revenue), 2) AS revenue_generated
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.id
        ORDER BY units_sold DESC, revenue_generated DESC
        LIMIT ?
        """,
        (top_n,),
    )
    top_products = [dict(row) for row in cursor.fetchall()]

    return {
        "total_revenue": round(totals["total_revenue"], 2),
        "total_profit": round(totals["total_profit"], 2),
        "total_sales_count": totals["total_sales_count"],
        "top_selling_products": top_products,
    }
