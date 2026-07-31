import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE SETUP ---
conn = sqlite3.connect("inventory.db", check_same_thread=False)
c = conn.cursor()

# Create tables for Master Inventory, School Allocations, and Messages/Appointments
c.execute(
    """CREATE TABLE IF NOT EXISTS master_inventory 
             (book_title TEXT PRIMARY KEY, central_stock INTEGER)"""
)
c.execute(
    """CREATE TABLE IF NOT EXISTS school_inventory 
             (school_name TEXT, book_title TEXT, quantity_received INTEGER, status TEXT, 
              PRIMARY KEY (school_name, book_title))"""
)
c.execute(
    """CREATE TABLE IF NOT EXISTS appointments 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, school_name TEXT, date TEXT, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"""
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

    # Change "admin123" to your preferred password
    CUSTODIAN_PASSWORD = "admin123"

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
                                "INSERT INTO school_inventory (school_name, book_title, quantity_received, status) VALUES (?, ?, ?, 'Dispatched') "
                                "ON CONFLICT(school_name, book_title) DO UPDATE SET quantity_received = quantity_received + ?",
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

        # Display Data Tables
        tab1, tab2, tab3 = st.tabs(
            [
                "📊 Central Warehouse Stock",
                "🚚 Dispatched Inventory Log",
                "📅 Scheduled Appointments / Messages",
            ]
        )

        with tab1:
            st.dataframe(
                pd.read_sql_query("SELECT * FROM master_inventory", conn),
                use_container_width=True,
            )

        with tab2:
            st.dataframe(
                pd.read_sql_query("SELECT * FROM school_inventory", conn),
                use_container_width=True,
            )

        with tab3:
            appointments_df = pd.read_sql_query(
                "SELECT school_name AS 'School', date AS 'Requested Date', message AS 'Message / Reason', timestamp AS 'Sent At' FROM appointments ORDER BY id DESC",
                conn,
            )
            if not appointments_df.empty:
                st.dataframe(appointments_df, use_container_width=True)
            else:
                st.info("No appointment requests or messages yet.")

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
            "SELECT book_title AS 'Book Title', quantity_received AS 'Quantity Allocated' FROM school_inventory WHERE school_name = ?",
            conn,
            params=(selected_school,),
        )

        st.subheader(f"Incoming / Assigned Books for {selected_school}")
        st.dataframe(school_df, use_container_width=True)

        st.divider()

        # NEW: SCHEDULE AN APPOINTMENT / MESSAGE SECTION
        st.subheader("📅 Schedule an Appointment / Message Custodian")
        st.write(
            "Need to pick up books, make a request, or schedule a meeting? Send a message below."
        )

        with st.form("appointment_form"):
            appt_date = st.date_input("Preferred Appointment Date")
            message = st.text_area(
                "Message / Notes for Custodian",
                placeholder="e.g., Requesting to pick up 30 extra Grade 2 Math books this Thursday at 10:00 AM.",
            )
            submit_appt = st.form_submit_button("Send Request to Custodian")

            if submit_appt:
                if message.strip() == "":
                    st.warning("Please enter a message before sending.")
                else:
                    c.execute(
                        "INSERT INTO appointments (school_name, date, message) VALUES (?, ?, ?)",
                        (selected_school, str(appt_date), message.strip()),
                    )
                    conn.commit()
                    st.success(
                        "Your appointment request/message has been sent to the Custodian!"
                    )
