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

# Check if old table exists without 'id' column and upgrade it safely
c.execute("PRAGMA table_info(school_inventory)")
columns = [column[1] for column in c.fetchall()]

if "id" not in columns and len(columns) > 0:
    # Drop old table format so it can be recreated with ID
    c.execute("DROP TABLE school_inventory")

c.execute(
    """CREATE TABLE IF NOT EXISTS school_inventory 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, school_name TEXT, book_title TEXT, quantity_received INTEGER, status TEXT)"""
)

c.execute(
    """CREATE TABLE IF NOT EXISTS appointments 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, school_name TEXT, date TEXT, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"""
)
conn.commit()

# --- PRESET SCHOOL LIST ---
SCHOOL_LIST = [
    "Arcaflor Maniapao ES",
    "Balabag ES",
    "Casildo B. Nonol Sr. ES",
    "Colorado ES",
    "Damñas ES",
    "Digos City Central ES",
    "Domingo Abawag ES",
    "Dulangan ES",
    "Federico Alferez ES",
    "Jolencio R. Alberca ES",
    "Lungag ES",
    "Mahayahay ES",
    "Pedro Basalan ES",
    "Ranao ES",
    "Remedios N. Saplala ES",
    "Ruparan ES",
]

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

    password = st.text_input(
        "Enter Custodian Password to Access:", type="password"
    )
    CUSTODIAN_PASSWORD = "admin123"  # Change this to your preferred password!

    if password == CUSTODIAN_PASSWORD:
        st.success("Access Granted!")

        col1, col2 = st.columns([1, 2])

        # 1. Add new books to central storage
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
                    st.rerun()

        # 2. Dispatch Books Grid
        with col2:
            st.subheader("Dispatch Books to Schools")
            master_df = pd.read_sql_query(
                "SELECT * FROM master_inventory", conn
            )

            if master_df.empty:
                st.info(
                    "Please add books to the Central Stock first before dispatching."
                )
            else:
                book_options = master_df["book_title"].tolist()

                h1, h2, h3, h4 = st.columns([2.5, 3, 2, 2])
                h1.markdown("**School Name**")
                h2.markdown("**Select Book**")
                h3.markdown("**Quantity**")
                h4.markdown("**Action**")
                st.divider()

                for idx, school in enumerate(SCHOOL_LIST):
                    c1, c2, c3, c4 = st.columns([2.5, 3, 2, 2])
                    c1.write(school)
                    selected_book = c2.selectbox(
                        f"Book for {school}",
                        book_options,
                        key=f"dispatch_book_{idx}",
                        label_visibility="collapsed",
                    )
                    qty = c3.number_input(
                        f"Qty for {school}",
                        min_value=1,
                        step=1,
                        value=10,
                        key=f"dispatch_qty_{idx}",
                        label_visibility="collapsed",
                    )

                    if c4.button(
                        "Dispatch", key=f"dispatch_btn_{idx}", type="primary"
                    ):
                        current_stock = master_df.loc[
                            master_df["book_title"] == selected_book,
                            "central_stock",
                        ].values[0]

                        if qty > current_stock:
                            st.error(
                                f"Not enough stock! Only {current_stock} available."
                            )
                        else:
                            c.execute(
                                "UPDATE master_inventory SET central_stock = central_stock - ? WHERE book_title = ?",
                                (qty, selected_book),
                            )
                            c.execute(
                                "INSERT INTO school_inventory (school_name, book_title, quantity_received, status) VALUES (?, ?, ?, 'Pending')",
                                (school, selected_book, qty),
                            )
                            conn.commit()
                            st.success(
                                f"Dispatched {qty} of '{selected_book}' to {school}!"
                            )
                            st.rerun()

        st.divider()

        # Display Data Tabs
        tab1, tab2, tab3 = st.tabs(
            [
                "📊 Central Warehouse Stock",
                "🚚 Interactive Dispatched Inventory Log",
                "📅 Scheduled Appointments / Messages",
            ]
        )

        with tab1:
            st.dataframe(
                pd.read_sql_query("SELECT * FROM master_inventory", conn),
                use_container_width=True,
            )

        # INTERACTIVE DISPATCHED INVENTORY LOG
        with tab2:
            st.subheader("Manage Dispatched Inventory")
            dispatched_df = pd.read_sql_query(
                "SELECT * FROM school_inventory", conn
            )

            if dispatched_df.empty:
                st.info("No dispatched inventory records found.")
            else:
                master_df = pd.read_sql_query(
                    "SELECT * FROM master_inventory", conn
                )
                all_books = master_df["book_title"].tolist()

                # Table Header
                col_sch, col_bk, col_qty, col_st, col_act = st.columns(
                    [2.5, 3, 1.5, 1.5, 2]
                )
                col_sch.markdown("**List of Schools**")
                col_bk.markdown("**Select Book (option bar)**")
                col_qty.markdown("**Quantity / Edit**")
                col_st.markdown("**Status**")
                col_act.markdown("**Actions**")
                st.divider()

                for index, row in dispatched_df.iterrows():
                    r_id = row["id"]
                    r_school = row["school_name"]
                    r_book = row["book_title"]
                    r_qty = row["quantity_received"]
                    r_status = row["status"]

                    c_sch, c_bk, c_qty, c_st, c_act = st.columns(
                        [2.5, 3, 1.5, 1.5, 2]
                    )

                    c_sch.write(r_school)

                    # Option bar to edit book title if mistake was made
                    book_idx = (
                        all_books.index(r_book) if r_book in all_books else 0
                    )
                    updated_book = c_bk.selectbox(
                        f"Book {r_id}",
                        all_books,
                        index=book_idx,
                        key=f"edit_bk_{r_id}",
                        label_visibility="collapsed",
                    )

                    # Number box to edit quantity directly
                    updated_qty = c_qty.number_input(
                        f"Qty {r_id}",
                        min_value=1,
                        value=int(r_qty),
                        key=f"edit_qty_{r_id}",
                        label_visibility="collapsed",
                    )

                    # Display status badge
                    if r_status == "Received":
                        c_st.markdown("🟢 **Received**")
                    else:
                        c_st.markdown("🟡 **Pending**")

                    btn_col1, btn_col2 = c_act.columns(2)

                    # 1. Save Edit Button
                    if (updated_book != r_book) or (updated_qty != r_qty):
                        if btn_col1.button("💾 Save", key=f"save_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET book_title = ?, quantity_received = ? WHERE id = ?",
                                (updated_book, updated_qty, r_id),
                            )
                            conn.commit()
                            st.success("Updated record!")
                            st.rerun()

                    # 2. Mark as Received Button
                    if r_status == "Pending":
                        if btn_col2.button("Mark Received", key=f"rec_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET status = 'Received' WHERE id = ?",
                                (r_id,),
                            )
                            conn.commit()
                            st.success(
                                f"Marked '{r_book}' for {r_school} as Received!"
                            )
                            st.rerun()

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

    selected_school = st.selectbox("Select Your School:", SCHOOL_LIST)

    school_df = pd.read_sql_query(
        "SELECT book_title AS 'Book Title', quantity_received AS 'Quantity Allocated', status AS 'Status' FROM school_inventory WHERE school_name = ?",
        conn,
        params=(selected_school,),
    )

    st.subheader(f"Incoming / Assigned Books for {selected_school}")
    if school_df.empty:
        st.info("No dispatches logged for this school yet.")
    else:
        st.dataframe(school_df, use_container_width=True)

    st.divider()

    # SCHEDULE AN APPOINTMENT / MESSAGE SECTION
    st.subheader("📅 Schedule an Appointment / Message Custodian")
    st.write(
        "Need to pick up books, make a request, or schedule a meeting? Send a message below."
    )

    with st.form("appointment_form"):
        appt_date = st.date_input("Preferred Appointment Date")
        message = st.text_area(
            "Message / Notes for Custodian",
            placeholder="e.g., Requesting to pick up 30 extra Grade 3 Science books this Thursday at 10:00 AM.",
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
