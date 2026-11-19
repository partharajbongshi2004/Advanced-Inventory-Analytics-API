from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from database import get_db_connection, init_db

st.set_page_config(page_title="Inventory & Analytics", page_icon="👕", layout="wide")
init_db()

menu = st.sidebar.radio("Menu", ["Analytics & Inventory", "Add Product", "Record Sale"])

if menu == "Analytics & Inventory":
    st.title("📊 Analytics & Inventory")
    conn = get_db_connection()
    products = pd.read_sql_query("SELECT * FROM products", conn)
    sales = conn.execute("SELECT COALESCE(SUM(total_revenue),0), COALESCE(SUM(total_profit),0) FROM sales").fetchone()
    conn.close()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Revenue", f"${sales[0]:,.2f}")
    c2.metric("Total Net Profit", f"${sales[1]:,.2f}")
    c3.metric("Total Stock", int(products["stock"].sum()) if not products.empty else 0)

    if not products.empty:
        low = products[products["stock"] <= products["min_stock_threshold"]]
        if not low.empty:
            st.warning("⚠️ Low-Stock Products")
            st.dataframe(low, use_container_width=True, hide_index=True)
        st.subheader("📦 Full Inventory")
        st.dataframe(products, use_container_width=True, hide_index=True)

elif menu == "Add Product":
    st.title("➕ Add Product")
    with st.form("add", clear_on_submit=True):
        name = st.text_input("Name")
        cat = st.text_input("Category", "Tops")
        size = st.selectbox("Size", ["XS", "S", "M", "L", "XL", "XXL"])
        price = st.number_input("Price", min_value=0.1, value=25.0)
        cost = st.number_input("Cost Price", min_value=0.0, value=10.0)
        stock = st.number_input("Stock", min_value=0, step=1, value=10)
        thresh = st.number_input("Min Stock Threshold", min_value=0, step=1, value=5)

        if st.form_submit_button("Save Product") and name.strip():
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO products (name, category, size, price, cost_price, stock, min_stock_threshold) VALUES (?,?,?,?,?,?,?)",
                (name.strip(), cat.strip(), size, price, cost, stock, thresh),
            )
            conn.commit()
            conn.close()
            st.success(f"{name} added!")

elif menu == "Record Sale":
    st.title("🛒 Record Sale")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM products WHERE stock > 0", conn)
    conn.close()

    if df.empty:
        st.warning("No stock available!")
    else:
        options = {f"{r['name']} ({r['size']}) - ${r['price']} [Stock: {r['stock']}]": r for _, r in df.iterrows()}
        choice = st.selectbox("Select Product", list(options.keys()))
        item = options[choice]
        qty = st.number_input("Quantity", min_value=1, max_value=int(item["stock"]), step=1)

        if st.button("Complete Sale"):
            rev = round(float(item["price"]) * qty, 2)
            prof = round((float(item["price"]) - float(item["cost_price"])) * qty, 2)
            conn = get_db_connection()
            conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, int(item["id"])))
            conn.execute(
                "INSERT INTO sales (product_id, quantity, total_revenue, total_profit, sale_date) VALUES (?,?,?,?,?)",
                (int(item["id"]), qty, rev, prof, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
            st.success(f"Sold {qty}x {item['name']} | Revenue: ${rev} | Profit: ${prof}")
            st.rerun()
