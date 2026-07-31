import sqlite3
import pandas as pd
import streamlit as st

# ==========================================
# 1. DATABASE SETUP (SAFE INITIALIZATION)
# ==========================================
conn = sqlite3.connect("inventory.db", check_same_thread=False)
c = conn.cursor()

# Master stock table
c.execute(
    """CREATE TABLE IF NOT EXISTS master_inventory 
       (book_title TEXT PRIMARY KEY, central_stock INTEGER)"""
)

# School inventory table
c.execute(
    """CREATE TABLE IF NOT EXISTS school_inventory 
       (id INTEGER PRIMARY KEY AUTOINCREMENT, 
        school_name TEXT, 
        book_title TEXT, 
        quantity_received INTEGER, 
        status TEXT)"""
)

# Appointments table
c.execute(
    """CREATE TABLE IF NOT EXISTS appointments 
       (id INTEGER PRIMARY KEY AUTOINCREMENT, 
        school_name TEXT, 
        date TEXT, 
        message TEXT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"""
)

conn.commit()

# ==========================================
# 2. PRESET SCHOOL LIST & PAGE CONFIG
# ==========================================
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

st.set_page_config(page_title="District Book Inventory", layout="wide")
st.title("📚 District Book Inventory Tracker")

# Sidebar navigation
role = st.sidebar.radio("Select View:", ["Principal View", "Custodian View"])

# ==========================================
# 3. CUSTODIAN VIEW (PROTECTED)
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

        # --- A. ADD NEW BOOKS TO CENTRAL STORAGE ---
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

# --- B. DISPATCH BOOKS GRID (WITH INSTANT LIVE MONITORING) ---
        with col2:
            st.subheader("Dispatch Books to Schools")
            master_df = pd.read_sql_query("SELECT * FROM master_inventory", conn)

            if master_df.empty:
                st.info("Please add books to Central Stock first before dispatching.")
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

                # Fetch current warehouse stock
                current_stock = master_df.loc[
                    master_df["book_title"] == selected_book, "central_stock"
                ].values[0]

                st.divider()

                # Table Header
                h1, h2, h3 = st.columns([4, 2, 2])
                h1.markdown("**School Name**")
                h2.markdown("**Quantity**")
                h3.markdown("**Action**")
                st.divider()

                live_total_requested = 0
                dispatch_selections = []

                for idx, school in enumerate(SCHOOL_LIST):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    c1.write(f"**{school}**")

                    # Key for dynamic state tracking
                    input_key = f"dispatch_qty_{selected_book}_{idx}"

                    # Initialize default value in session state if not set
                    if input_key not in st.session_state:
                        st.session_state[input_key] = 10

                    qty = c2.number_input(
                        f"Qty for {school}",
                        min_value=1,
                        step=1,
                        key=input_key,
                        label_visibility="collapsed",
                    )

                    # Accurately sum values currently stored in state
                    live_total_requested += st.session_state[input_key]

                    dispatch_selections.append({"school": school, "qty": qty})

                    # Individual Dispatch Button
                    if c3.button("Dispatch", key=f"dispatch_btn_{idx}"):
                        if qty > current_stock:
                            st.error(f"Not enough stock! Only {current_stock} available.")
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
                            st.success(f"Dispatched {qty} copies of '{selected_book}' to {school}!")
                            st.rerun()

                # LIVE MONITORING METRICS BANNER
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("📦 Warehouse Stock Available", current_stock)
                m2.metric("📋 Total Input (All Schools)", live_total_requested)

                remaining_after_batch = current_stock - live_total_requested
                if remaining_after_batch >= 0:
                    m3.metric("🟢 Remaining Stock After Batch", remaining_after_batch)
                else:
                    m3.metric("🔴 Stock Deficit", remaining_after_batch, delta_color="inverse")
                    st.error(
                        f"⚠️ Warning: Total requested quantity ({live_total_requested}) exceeds available warehouse stock ({current_stock}) by {abs(remaining_after_batch)} books!"
                    )

                # BATCH DISPATCH ALL LOGIC
                if dispatch_all_btn:
                    if live_total_requested > current_stock:
                        st.error(
                            f"Cannot batch dispatch! Required `{live_total_requested}` copies of **{selected_book}**, but only `{current_stock}` available in central stock."
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
                            f"Successfully batch dispatched **{selected_book}** ({live_total_requested} total copies) to all {len(SCHOOL_LIST)} schools!"
                        )
                        st.rerun()
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

                # Fetch current warehouse stock
                current_stock = master_df.loc[
                    master_df["book_title"] == selected_book,
                    "central_stock",
                ].values[0]

                live_total_requested = 0
                dispatch_selections = []

                st.divider()

                # Table Header
                h1, h2, h3 = st.columns([4, 2, 2])
                h1.markdown("**School Name**")
                h2.markdown("**Quantity**")
                h3.markdown("**Action**")
                st.divider()

                for idx, school in enumerate(SCHOOL_LIST):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    c1.write(f"**{school}**")

                    qty = c2.number_input(
                        f"Qty for {school}",
                        min_value=1,
                        step=1,
                        value=10,
                        key=f"dispatch_qty_{selected_book}_{idx}",
                        label_visibility="collapsed",
                    )

                    # Dynamic Monitoring Accumulator
                    live_total_requested += qty

                    dispatch_selections.append(
                        {
                            "school": school,
                            "qty": qty,
                        }
                    )

                    # Individual Dispatch Button
                    if c3.button("Dispatch", key=f"dispatch_btn_{idx}"):
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

                # LIVE MONITORING METRICS BANNER
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("📦 Warehouse Available Stock", current_stock)
                m2.metric("📋 Live Input Total (All Schools)", live_total_requested)

                remaining_after_batch = current_stock - live_total_requested
                if remaining_after_batch >= 0:
                    m3.metric("🟢 Stock Remaining After Batch", remaining_after_batch)
                else:
                    m3.metric("🔴 Stock Deficit", remaining_after_batch, delta_color="inverse")
                    st.error(
                        f"⚠️ Warning: Total input quantity ({live_total_requested}) exceeds available stock ({current_stock}) by {abs(remaining_after_batch)} books!"
                    )

                # BATCH DISPATCH ALL LOGIC
                if dispatch_all_btn:
                    if live_total_requested > current_stock:
                        st.error(
                            f"Cannot batch dispatch! Required `{live_total_requested}` copies of **{selected_book}**, but only `{current_stock}` available in central stock."
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
                            f"Successfully batch dispatched **{selected_book}** ({live_total_requested} total copies) to all {len(SCHOOL_LIST)} schools!"
                        )
                        st.rerun()

        st.divider()

        # --- C. DATA & MANAGEMENT TABS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "📊 Central Warehouse Stock",
                "🚚 Dispatched Inventory Log",
                "🗑️ Delete Inventory",
                "📖 Track Inventory by Title",
                "📅 Scheduled Appointments / Messages",
            ]
        )

        # TAB 1: Warehouse Stock
        with tab1:
            st.subheader("📊 Central Warehouse Stock")
            central_df = pd.read_sql_query("SELECT * FROM master_inventory", conn)

            if central_df.empty:
                st.info("No books in central warehouse stock.")
            else:
                st.dataframe(central_df, use_container_width=True)

                with st.expander("🗑️ Delete Book Title from Central Storage"):
                    del_book_title = st.selectbox(
                        "Select Book Title to Delete permanently from Master Stock:",
                        central_df["book_title"].tolist(),
                        key="del_master_select",
                    )
                    if st.button("Delete Master Book Title", type="primary"):
                        c.execute(
                            "DELETE FROM master_inventory WHERE book_title = ?",
                            (del_book_title,),
                        )
                        conn.commit()
                        st.success(
                            f"Deleted '{del_book_title}' from central warehouse!"
                        )
                        st.rerun()

        # TAB 2: Dispatched Log
        with tab2:
            st.subheader("Manage Dispatched Inventory")

            dispatched_df = pd.read_sql_query(
                "SELECT rowid AS id, school_name, book_title, quantity_received, status FROM school_inventory",
                conn,
            )

            if dispatched_df.empty:
                st.info("No dispatched inventory records found.")
            else:
                col_sch, col_bk, col_qty, col_st, col_act = st.columns(
                    [2.5, 2.5, 1.5, 1.2, 2.3]
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
                        [2.5, 2.5, 1.5, 1.2, 2.3]
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

                    btn_col1, btn_col2, btn_col3 = c_act.columns([1, 1.2, 1])

                    if updated_qty != r_qty:
                        if btn_col1.button("💾 Save", key=f"save_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET quantity_received = ? WHERE rowid = ?",
                                (updated_qty, r_id),
                            )
                            conn.commit()
                            st.success("Updated record!")
                            st.rerun()

                    if r_status == "Pending":
                        if btn_col2.button("Received", key=f"rec_{r_id}"):
                            c.execute(
                                "UPDATE school_inventory SET status = 'Received' WHERE rowid = ?",
                                (r_id,),
                            )
                            conn.commit()
                            st.success(
                                f"Marked '{r_book}' for {r_school} as Received!"
                            )
                            st.rerun()

                    if btn_col3.button("🗑️", key=f"del_row_{r_id}", help="Delete this entry"):
                        c.execute(
                            "DELETE FROM school_inventory WHERE rowid = ?",
                            (r_id,),
                        )
                        conn.commit()
                        st.success("Deleted record!")
                        st.rerun()

        # TAB 3: Delete Inventory Menu
        with tab3:
            st.subheader("🗑️ Delete Inventory Records")
            st.write("Manage or wipe specific dispatched records from the system.")

            dispatched_df = pd.read_sql_query(
                "SELECT rowid AS id, school_name, book_title, quantity_received, status FROM school_inventory",
                conn,
            )

            if dispatched_df.empty:
                st.info("No dispatched inventory available to delete.")
            else:
                d_col1, d_col2 = st.columns(2)

                # Option A: Delete Single Record
                with d_col1:
                    st.markdown("### Delete Specific Entry")
                    records = [
                        f"ID {r['id']} - {r['school_name']} | {r['book_title']} ({r['quantity_received']} copies)"
                        for _, r in dispatched_df.iterrows()
                    ]
                    selected_record = st.selectbox(
                        "Select Record to Delete:", records, key="del_single_select"
                    )

                    if st.button("Delete Selected Record", type="primary", key="btn_del_single"):
                        record_id = int(selected_record.split(" ")[1])
                        c.execute(
                            "DELETE FROM school_inventory WHERE rowid = ?",
                            (record_id,),
                        )
                        conn.commit()
                        st.success(f"Record ID {record_id} deleted successfully!")
                        st.rerun()

                # Option B: Clear All Records for a School
                with d_col2:
                    st.markdown("### Clear All Records for a School")
                    del_school = st.selectbox(
                        "Select School to Wipe Dispatches:", SCHOOL_LIST, key="del_school_select"
                    )

                    if st.button(f"Clear All Records for {del_school}", type="primary", key="btn_del_school"):
                        c.execute(
                            "DELETE FROM school_inventory WHERE TRIM(school_name) = TRIM(?)",
                            (del_school,),
                        )
                        conn.commit()
                        st.success(
                            f"All dispatched records for '{del_school}' cleared!"
                        )
                        st.rerun()

        # TAB 4: Track Inventory by Book Title
        with tab4:
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

        # TAB 5: Appointments / Messages
        with tab5:
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
# 4. PRINCIPAL VIEW (PUBLIC)
# ==========================================
else:
    st.header("Principal Portal")

    selected_school = st.selectbox("Select Your School:", SCHOOL_LIST)

    # Grouped query with TRIM to prevent missing books due to spaces
    school_df = pd.read_sql_query(
        """SELECT 
            book_title AS 'Book Title', 
            SUM(quantity_received) AS 'Total Quantity Allocated', 
            status AS 'Status' 
           FROM school_inventory 
           WHERE TRIM(school_name) = TRIM(?)
           GROUP BY book_title, status""",
        conn,
        params=(selected_school,),
    )

    st.subheader(f"📦 Incoming / Assigned Books for {selected_school}")
    if school_df.empty:
        st.info(
            "ℹ️ No dispatches logged for this school yet.\n\n"
            "**Note for Custodians:** Books added to Central Storage only appear here AFTER clicking **'Dispatch'** or **'Batch Dispatch All'**."
        )
    else:
        st.dataframe(school_df, use_container_width=True)

    st.divider()

    # Schedule Appointment Section
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
