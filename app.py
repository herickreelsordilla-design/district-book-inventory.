import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE SETUP ---
conn = sqlite3.connect("inventory.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """CREATE TABLE IF NOT EXISTS master_inventory 
             (book_title TEXT PRIMARY KEY, central_stock INTEGER)"""
)
c.execute(
    """CREATE TABLE IF NOT EXISTS school_inventory 
             (school_name TEXT, book_title TEXT, quantity_received INTEGER, status TEXT, 
              PRIMARY KEY (school_name, book_title))"""
)
conn.commit()

# --- APP LAYOUT ---
st.set_page_config(page_title="District Book Inventory", layout="wide")
st.title("📚 District Book Inventory Tracker")

# Sidebar navigation
role = st.sidebar.radio("Select View:", ["Principal View", "Custodian View"])

# ==========================================
# CUSTODIAN VIEW (PROTECTED)
# ==========================================
if role == "Custodian View":
    st.header("🔒 Custodian Control Panel")

    # Simple Password Lock
    password = st.text_input(
        "Enter Custodian Password to Access:", type="password"
    )

    # Change "admin123" to whatever secret password you want!
    CUSTODIAN_PASSWORD = "adminHERICKreel"

    if password == CUSTODIAN_PASSWORD:
        st.success("Access Granted!")

        col1, col2 = st.columns(2)

        # 1. Add new books
        with col1:
            st.subheader("Add / Update Central Stock")
            with st.form("add_book_form"):
                title = st.text_input("Book Title")
                stock = st.number_input(
                    "Quantity to Add", min_value=1, step=1, value=100
                )
                submit = st.form_submit_button("Add to Master Stock")

                if submit and title:
                    c.execute(
                        "INSERT INTO master_inventory (book_title, central_stock) VALUES (?, ?) "
                        "ON CONFLICT(book_title) DO UPDATE SET central_stock = central_stock + ?",
                        (title.strip(), stock, stock),
                    )
                    conn.commit()
                    st.success(f"Added {stock} copies of '{title}'!")

        # 2. Dispatch books
        with col2:
            st.subheader("Dispatch Books to a School")
            master_df = pd.read_sql_query(
                "SELECT * FROM master_inventory", conn
            )

            if not master_df.empty:
                with st.form("dispatch_form"):
                    selected_book = st.selectbox(
                        "Select Book", master_df["book_title"].tolist()
                    )
                    school_name = st.text_input(
                        "School / Principal Name",
                        placeholder="e.g. Lincoln High",
                    )
                    dispatch_qty = st.number_input(
                        "Quantity to Send", min_value=1, step=1, value=10
                    )
                    dispatch_submit = st.form_submit_button(
                        "Dispatch to Principal"
                    )

                    if dispatch_submit and school_name:
                        current_stock = master_df.loc[
                            master_df["book_title"] == selected_book,
                            "central_stock",
                        ].values[0]

                        if dispatch_qty > current_stock:
                            st.error("Not enough central stock available!")
                        else:
                            c.execute(
                                "UPDATE master_inventory SET central_stock = central_stock - ? WHERE book_title = ?",
                                (dispatch_qty, selected_book),
                            )
                            c.execute(
                                "INSERT INTO school_inventory (school_name, book_title, quantity_received, status) VALUES (?, ?, ?, 'Pending') "
                                "ON CONFLICT(school_name, book_title) DO UPDATE SET quantity_received = quantity_received + ?, status = 'Pending'",
                                (
                                    school_name.strip(),
                                    selected_book,
                                    dispatch_qty,
                                    dispatch_qty,
                                ),
                            )
                            conn.commit()
                            st.success(
                                f"Dispatched {dispatch_qty} of '{selected_book}' to {school_name}!"
                            )
                            st.rerun()

        st.divider()

        # Display Tables
        st.subheader("📊 Central Warehouse Stock")
        st.dataframe(
            pd.read_sql_query("SELECT * FROM master_inventory", conn),
            use_container_width=True,
        )

        st.subheader("🚚 Dispatched Inventory Log")
        st.dataframe(
            pd.read_sql_query("SELECT * FROM school_inventory", conn),
            use_container_width=True,
        )

    elif password != "":
        st.error("Incorrect Password. Access Denied.")
    else:
        st.info("Please enter the custodian password above to unlock controls.")

# ==========================================
# PRINCIPAL VIEW (PUBLIC)
# ==========================================
else:
    st.header("Principal Portal")

    all_schools = pd.read_sql_query(
        "SELECT DISTINCT school_name FROM school_inventory", conn
    )["school_name"].tolist()

    if not all_schools:
        st.info("No dispatches logged yet.")
    else:
        selected_school = st.selectbox("Select Your School:", all_schools)

        school_df = pd.read_sql_query(
            "SELECT book_title, quantity_received, status FROM school_inventory WHERE school_name = ?",
            conn,
            params=(selected_school,),
        )

        st.subheader(f"Incoming / Assigned Books for {selected_school}")
        st.dataframe(school_df, use_container_width=True)

        pending_books = school_df[school_df["status"] == "Pending"][
            "book_title"
        ].tolist()

        if pending_books:
            st.subheader("Acknowledge Delivery")
            book_to_confirm = st.selectbox(
                "Select book received:", pending_books
            )
            if st.button("Confirm Receipt"):
                c.execute(
                    "UPDATE school_inventory SET status = 'Received' WHERE school_name = ? AND book_title = ?",
                    (selected_school, book_to_confirm),
                )
                conn.commit()
                st.success(f"Status for '{book_to_confirm}' updated to Received!")
                st.rerun()
