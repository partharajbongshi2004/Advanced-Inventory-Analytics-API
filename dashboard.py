from datetime import datetime, timezone
import sqlite3
import pandas as pd
import streamlit as st

from database import get_db_connection, init_db

# --- Page Configuration ---
st.set_page_config(
    page_title="Clothing Store Inventory & Analytics",
    page_icon="👕",
    layout="wide",
)

# --- Initialize Database Automatically ---
init_db()


# --- Helper Functions ---
def fetch_products() -> pd.DataFrame:
    """Fetches all products from the SQLite database as a pandas DataFrame."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM products ORDER BY id DESC", conn)
    finally:
        conn.close()
    return df


def fetch_sales_summary() -> dict:
    """Fetches total revenue and total profit from the sales table."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(total_revenue), 0.0) AS total_revenue,
                COALESCE(SUM(total_profit), 0.0) AS total_profit
            FROM sales
            """
        )
        row = cursor.fetchone()
        return {
            "total_revenue": float(row["total_revenue"]),
            "total_profit": float(row["total_profit"]),
        }
    finally:
        conn.close()


# --- Sidebar Navigation ---
st.sidebar.title("👕 Store Manager")
st.sidebar.markdown("Manage clothing inventory, record sales, and track profits.")

menu = st.sidebar.radio(
    "Navigation",
    options=["Analytics & Inventory", "Add Product", "Record Sale"],
    index=0,
)

# ==========================================
# 1. ANALYTICS & INVENTORY VIEW
# ==========================================
if menu == "Analytics & Inventory":
    st.title("📊 Analytics & Inventory Overview")

    products_df = fetch_products()
    sales_summary = fetch_sales_summary()

    total_stock = int(products_df["stock"].sum()) if not products_df.empty else 0

    # Key Metrics Row
    col1, col2, col3 = st.columns(3)
    col1.metric(
        label="Total Revenue",
        value=f"${sales_summary['total_revenue']:,.2f}",
    )
    col2.metric(
        label="Total Net Profit",
        value=f"${sales_summary['total_profit']:,.2f}",
    )
    col3.metric(
        label="Total Items in Stock",
        value=f"{total_stock:,}",
    )

    st.divider()

    # Low-Stock Alerts Section (stock <= min_stock_threshold)
    st.subheader("⚠️ Low-Stock Alerts")
    if not products_df.empty:
        low_stock_df = products_df[
            products_df["stock"] <= products_df["min_stock_threshold"]
        ]
        if not low_stock_df.empty:
            st.warning(
                f"{len(low_stock_df)} product(s) are at or below their minimum stock threshold!"
            )
            st.dataframe(
                low_stock_df[
                    ["id", "name", "category", "size", "stock", "min_stock_threshold"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("All products are sufficiently stocked above minimum thresholds.")
    else:
        st.info("No products in inventory yet.")

    st.divider()

    # Full Inventory Table
    st.subheader("📦 Full Clothing Inventory")
    if not products_df.empty:
        # Optional quick filters for convenience
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            categories = ["All"] + sorted(products_df["category"].unique().tolist())
            selected_category = st.selectbox("Filter by Category", categories)
        with filter_col2:
            sizes = ["All"] + sorted(products_df["size"].unique().tolist())
            selected_size = st.selectbox("Filter by Size", sizes)

        filtered_df = products_df.copy()
        if selected_category != "All":
            filtered_df = filtered_df[filtered_df["category"] == selected_category]
        if selected_size != "All":
            filtered_df = filtered_df[filtered_df["size"] == selected_size]

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "name": "Product Name",
                "category": "Category",
                "size": "Size",
                "price": st.column_config.NumberColumn("Retail Price", format="$%.2f"),
                "cost_price": st.column_config.NumberColumn("Cost Price", format="$%.2f"),
                "stock": "In Stock",
                "min_stock_threshold": "Min Threshold",
            },
        )
    else:
        st.info("Your inventory is empty. Go to **Add Product** in the sidebar to add items.")

# ==========================================
# 2. ADD PRODUCT VIEW
# ==========================================
elif menu == "Add Product":
    st.title("➕ Add New Clothing Product")
    st.markdown("Enter product details below to add a new item to the inventory.")

    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Product Name *", placeholder="e.g., Classic Cotton T-Shirt")
            category = st.selectbox(
                "Category *",
                options=["Tops", "Bottoms", "Outerwear", "Dresses", "Activewear", "Accessories", "Footwear"],
            )
            size = st.selectbox(
                "Size *",
                options=["XS", "S", "M", "L", "XL", "XXL", "One Size"],
            )
            stock = st.number_input("Initial Stock Quantity *", min_value=0, step=1, value=10)

        with col2:
            price = st.number_input("Retail Price ($) *", min_value=0.01, step=0.50, value=29.99, format="%.2f")
            cost_price = st.number_input("Wholesale Cost Price ($) *", min_value=0.00, step=0.50, value=10.00, format="%.2f")
            min_stock_threshold = st.number_input("Minimum Stock Alert Threshold *", min_value=0, step=1, value=5)

        submitted = st.form_submit_button("Save Product", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Product Name is required.")
            else:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO products (name, category, size, price, cost_price, stock, min_stock_threshold)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name.strip(),
                            category,
                            size,
                            round(float(price), 2),
                            round(float(cost_price), 2),
                            int(stock),
                            int(min_stock_threshold),
                        ),
                    )
                    conn.commit()
                    st.success(f"Successfully added **{name.strip()}** (Size: {size}) to inventory!")
                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"Database error: {e}")
                finally:
                    conn.close()

# ==========================================
# 3. RECORD SALE VIEW
# ==========================================
elif menu == "Record Sale":
    st.title("🛒 Record a Sale")
    st.markdown("Select an in-stock product and enter the quantity sold.")

    products_df = fetch_products()
    available_df = products_df[products_df["stock"] > 0] if not products_df.empty else pd.DataFrame()

    if available_df.empty:
        st.warning("No products with available stock! Please add products or restock existing ones first.")
    else:
        # Build readable labels mapped to product rows
        product_options = {
            f"{row['name']} | Size: {row['size']} | ${row['price']:.2f} ({row['stock']} in stock)": row
            for _, row in available_df.iterrows()
        }

        selected_label = st.selectbox("Select Product", options=list(product_options.keys()))
        selected_product = product_options[selected_label]

        max_qty = int(selected_product["stock"])

        with st.form("record_sale_form"):
            quantity = st.number_input(
                "Quantity Sold",
                min_value=1,
                max_value=max_qty,
                value=1,
                step=1,
            )

            # Live financial preview
            est_revenue = round(float(selected_product["price"]) * quantity, 2)
            est_profit = round(
                (float(selected_product["price"]) - float(selected_product["cost_price"])) * quantity,
                2,
            )

            st.info(
                f"**Order Summary:** Revenue: **${est_revenue:,.2f}** | Estimated Profit: **${est_profit:,.2f}**"
            )

            sale_submitted = st.form_submit_button("Complete Sale", type="primary", use_container_width=True)

            if sale_submitted:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    # Re-verify current stock inside transaction
                    cursor.execute(
                        "SELECT stock, price, cost_price FROM products WHERE id = ?",
                        (int(selected_product["id"]),),
                    )
                    current_item = cursor.fetchone()

                    if not current_item or current_item["stock"] < quantity:
                        st.error("Insufficient stock available to complete this sale.")
                    else:
                        new_stock = current_item["stock"] - int(quantity)
                        total_revenue = round(float(current_item["price"]) * int(quantity), 2)
                        total_profit = round(
