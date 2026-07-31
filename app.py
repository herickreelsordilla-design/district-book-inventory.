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

# Auto-upgrade database structure if missing ID column
c.execute("PRAGMA table_info(school_inventory)")
columns = [column[1] for column in c.fetchall()]

if "id" not in columns and len(columns) > 0:
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
    CUSTODIAN_PASSWORD = "admin123"  # Change this password as needed

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

        # 2. DISPATCH BOOKS GRID (NO ROW DROPDOWNS)
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

                # MAIN DROP BAR TO SELECT BOOK TITLE
                m_col1, m_col2 = st.columns([3, 1])
                selected_book = m_col1.selectbox(
                    "📖 Select Book Title to Dispatch:",
                    book_options,
                    key="dispatch_book_select",
                )
                dispatch_all_btn = m_col2.button(
                    "⚡ Batch Dispatch All", type="primary", use_container_width=True
                )

                st.divider()

                # Table Header (3 Columns: School, Quantity, Action)
                h1, h2, h3 = st.columns([4, 2, 2])
                h1.markdown("**School Name**")
                h2.markdown("**Quantity**")
                h3.markdown("**Action**")
                st.divider()

                dispatch_selections = []

                for idx, school in enumerate(SCHOOL_LIST):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    c1.write(f"**{school}**")

                    qty = c2.number_input(
                        f"Qty for {school}",
                        min_value=1,
                        step=1,
                        value=10,
                        key=f"dispatch_qty_{idx}",
                        label_visibility="collapsed",
                    )

                    dispatch_selections.append(
                        {
                            "school": school,
                            "qty": qty,
                        }
                    )

                    # Individual Dispatch Button
                    if c3.button("Dispatch", key=f"dispatch_btn_{idx}"):
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
                                f"Dispatched {qty} copies of '{selected_book}' to {school}!"
                            )
                            st.rerun()

                # BATCH DISPATCH ALL LOGIC
                if dispatch_all_btn:
                    total_req = sum(item["qty"] for item in dispatch_selections)
                    current_stock = master_df.loc[
                        master_df["book_title"] == selected_book,
                        "central_stock",
                    ].values[0]

                    if total_req > current_stock:
                        st.error(
                            f"Cannot batch dispatch! Required `{total_req}` copies of **{selected_book}**, but only `{current_stock}` available in central stock."
                        )
                    else:
                        for item in dispatch_selections:
                            c.execute(
                                "UPDATE master_inventory SET central_stock = central_stock - ? WHERE book_title = ?",
                                (item["qty"], selected_book),
                            )
                            c.execute(
                                "INSERT INTO school_inventory (school_name, book_title, quantity_received, status) VALUES (?, ?, ?, 'Pending')",
                                (item["school"], selected_book, item["qty"]),
                            )
                        conn.commit()
                        st.success(
                            f"Successfully batch dispatched **{selected_book}** ({total_req} total copies) to all {len(SCHOOL_LIST)} schools!"
                        )
                        st.rerun()

        st.divider()

        # Display Data Tabs
        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "📊 Central Warehouse Stock",
                "🚚 Dispatched Inventory Log",
                "📖 Track Inventory by Book Title",
                "📅 Scheduled Appointments / Messages",
            ]
        )

        # TAB 1: Warehouse Stock
        with tab1:
            st.dataframe(
                pd.read_sql_query("SELECT * FROM master_inventory", conn),
                use_container_width=True,
            )

        # TAB 2: Dispatched Log
        with tab2:
            st.subheader("Manage Dispatched Inventory")
            dispatched_df = pd.read_sql_query(
                "SELECT * FROM school_inventory", conn
            )

            if dispatched_df.empty:
                st.info("No dispatched inventory records found.")
            else:
                col_sch, col_bk, col_qty, col_st, col_act = st.columns(
                    [2.5, 3, 1.5, 1.5, 2]
                )
                col_sch.markdown("**School Name**")
                col_bk.markdown("**Book Allocated**")
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

                    c_sch.write(f"**{r_school}**")
                    c_bk.write(r_book)

                    updated_qty = c_qty.number_input(
                        f"Qty {r_id}",
                        min_value=1,
                        value=int(r_qty),
                        key=f"edit_qty_{r_id}",
                        label_visibility="collapsed",
                    )

                    if r_status == "Received":
                        c_st.markdown("🟢 **Received**")
                    else:
                        c_st.markdown("🟡 **Pending**")

                    btn_col1, btn_col2 = c_act.columns(2)

                    if updated_qty != r_qty:
                        if btn_col1.button("💾 Save", key=f"save_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET quantity_received = ? WHERE id = ?",
                                (updated_qty, r_id),
                            )
                            conn.commit()
                            st.success("Updated record!")
                            st.rerun()

                    if r_status == "Pending":
                        if btn_col2.button("Received", key=f"rec_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET status = 'Received' WHERE id = ?",
                                (r_id,),
                            )
                            conn.commit()
                            st.success(
                                f"Marked '{r_book}' for {r_school} as Received!"
                            )
                            st.rerun()

        # TAB 3: BOOK TITLE DISTRIBUTION TRACKER
        with tab3:
            st.subheader("📖 Book Title Distribution Tracker")

            master_df = pd.read_sql_query(
                "SELECT * FROM master_inventory", conn
            )

            if master_df.empty:
                st.info("No books registered in the master stock yet.")
            else:
                all_titles = master_df["book_title"].tolist()
                selected_title = st.selectbox(
                    "Select a Book Title to Track:",
                    all_titles,
                    key="track_book_select",
                )

                if selected_title:
                    central_stock = master_df.loc[
                        master_df["book_title"] == selected_title,
                        "central_stock",
                    ].values[0]

                    book_dispatches = pd.read_sql_query(
                        "SELECT school_name AS 'School Name', quantity_received AS 'Quantity', status AS 'Status' FROM school_inventory WHERE book_title = ?",
                        conn,
                        params=(selected_title,),
                    )

                    total_dispatched = (
                        book_dispatches["Quantity"].sum()
                        if not book_dispatches.empty
                        else 0
                    )

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Central Warehouse Stock", central_stock)
                    m2.metric("Total Dispatched to Schools", total_dispatched)
                    m3.metric(
                        "Total District Inventory",
                        central_stock + total_dispatched,
                    )

                    st.divider()
                    st.write(
                        f"### School Breakdown for: **{selected_title}**"
                    )

                    if book_dispatches.empty:
                        st.info("This book has not been dispatched to any schools yet.")
                    else:
                        st.dataframe(book_dispatches, use_container_width=True)

        # TAB 4: Appointments / Messages
        with tab4:
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
