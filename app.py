from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="District Book Inventory", layout="wide")
st.title("📚 District Book Inventory Tracker")

# ==========================================
# 1. CONNECT TO GOOGLE SHEETS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper function to read a tab
def load_data(worksheet_name):
    return conn.read(worksheet=worksheet_name, ttl=0)

# ==========================================
# 2. PRESET SCHOOL LIST
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

# Sidebar navigation
role = st.sidebar.radio("Select View:", ["Principal View", "Custodian View"])

# ==========================================
# 3. CUSTODIAN VIEW
# ==========================================
if role == "Custodian View":
    st.header("🔒 Custodian Control Panel")

    password = st.text_input("Enter Custodian Password to Access:", type="password")
    CUSTODIAN_PASSWORD = "admin123"

    if password == CUSTODIAN_PASSWORD:
        st.success("Access Granted!")

        col1, col2 = st.columns([1, 2])

        # --- A. ADD NEW BOOKS TO CENTRAL STORAGE ---
        with col1:
            st.subheader("Add / Update Central Stock")
            with st.form("add_book_form"):
                title = st.text_input("Book Title")
                stock = st.number_input("Quantity to Add", min_value=1, step=1, value=100)
                submit = st.form_submit_button("Add to Master Stock")

                if submit and title:
                    master_df = load_data("master_inventory")
                    title_clean = title.strip()

                    if not master_df.empty and title_clean in master_df["book_title"].values:
                        master_df.loc[master_df["book_title"] == title_clean, "central_stock"] += stock
                    else:
                        new_row = pd.DataFrame([{"book_title": title_clean, "central_stock": stock}])
                        master_df = pd.concat([master_df, new_row], ignore_index=True)

                    conn.update(worksheet="master_inventory", data=master_df)
                    st.success(f"Added {stock} copies of '{title_clean}'!")
                    st.rerun()

        # --- B. DISPATCH BOOKS GRID ---
        with col2:
            st.subheader("Dispatch Books to Schools")
            master_df = load_data("master_inventory")

            if master_df.empty:
                st.info("Please add books to Central Stock first before dispatching.")
            else:
                master_df = master_df.sort_values(by="book_title", ascending=False)
                book_options = master_df["book_title"].tolist()

                m_col1, m_col2 = st.columns([3, 1])
                selected_book = m_col1.selectbox("📖 Select Book Title to Dispatch:", book_options)
                dispatch_all_btn = m_col2.button("⚡ Batch Dispatch All", type="primary", use_container_width=True)

                current_stock = int(master_df.loc[master_df["book_title"] == selected_book, "central_stock"].values[0])

                st.divider()

                live_total_requested = 0
                dispatch_selections = []

                for idx, school in enumerate(SCHOOL_LIST):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    c1.write(f"**{school}**")

                    input_key = f"dispatch_qty_{selected_book}_{idx}"
                    if input_key not in st.session_state:
                        st.session_state[input_key] = 10

                    qty = c2.number_input(
                        f"Qty for {school}",
                        min_value=1,
                        step=1,
                        key=input_key,
                        label_visibility="collapsed",
                    )
                    live_total_requested += qty
                    dispatch_selections.append({"school": school, "qty": qty})

                    if c3.button("Dispatch", key=f"dispatch_btn_{selected_book}_{idx}"):
                        if qty > current_stock:
                            st.error(f"Not enough stock! Only {current_stock} available.")
                        else:
                            # Update master inventory stock
                            master_df.loc[master_df["book_title"] == selected_book, "central_stock"] -= qty
                            conn.update(worksheet="master_inventory", data=master_df)

                            # Append to school inventory
                            school_df = load_data("school_inventory")
                            new_dispatch = pd.DataFrame([{
                                "school_name": school,
                                "book_title": selected_book,
                                "quantity_received": qty,
                                "status": "Pending"
                            }])
                            school_df = pd.concat([school_df, new_dispatch], ignore_index=True)
                            conn.update(worksheet="school_inventory", data=school_df)

                            st.success(f"Dispatched {qty} copies of '{selected_book}' to {school}!")
                            st.rerun()

                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("📦 Warehouse Stock Available", current_stock)
                m2.metric("📋 Total Input (All Schools)", live_total_requested)
                m3.metric("🟢 Remaining Stock After Batch", current_stock - live_total_requested)

                if dispatch_all_btn:
                    if live_total_requested > current_stock:
                        st.error(f"Cannot batch dispatch! Required `{live_total_requested}` copies, but only `{current_stock}` available.")
                    else:
                        master_df.loc[master_df["book_title"] == selected_book, "central_stock"] -= live_total_requested
                        conn.update(worksheet="master_inventory", data=master_df)

                        school_df = load_data("school_inventory")
                        new_rows = pd.DataFrame([
                            {
                                "school_name": item["school"],
                                "book_title": selected_book,
                                "quantity_received": item["qty"],
                                "status": "Pending"
                            } for item in dispatch_selections
                        ])
                        school_df = pd.concat([school_df, new_rows], ignore_index=True)
                        conn.update(worksheet="school_inventory", data=school_df)

                        st.success(f"Successfully batch dispatched **{selected_book}** to all schools!")
                        st.rerun()

        st.divider()

        # --- C. DATA & MANAGEMENT TABS ---
        tab1, tab2, tab3 = st.tabs(["📊 Central Warehouse Stock", "🚚 Dispatched Inventory Log", "📅 Scheduled Appointments"])

        with tab1:
            central_df = load_data("master_inventory")
            if not central_df.empty:
                st.dataframe(central_df.sort_values(by="book_title", ascending=False), use_container_width=True)

        with tab2:
            dispatched_df = load_data("school_inventory")
            if not dispatched_df.empty:
                st.dataframe(dispatched_df.sort_values(by="book_title", ascending=False), use_container_width=True)

        with tab3:
            appointments_df = load_data("appointments")
            if not appointments_df.empty:
                st.dataframe(appointments_df, use_container_width=True)

# ==========================================
# 4. PRINCIPAL VIEW
# ==========================================
else:
    st.header("Principal Portal")
    selected_school = st.selectbox("Select Your School:", SCHOOL_LIST)

    school_df = load_data("school_inventory")

    if not school_df.empty:
        filtered = school_df[school_df["school_name"].str.strip() == selected_school.strip()]
        if not filtered.empty:
            summary = filtered.groupby(["book_title", "status"])["quantity_received"].sum().reset_index()
            summary = summary.sort_values(by="book_title", ascending=False)
            st.dataframe(summary, use_container_width=True)
        else:
            st.info("No dispatches logged for this school yet.")

    st.divider()
    st.subheader("📅 Schedule an Appointment / Message Custodian")

    with st.form("appointment_form"):
        appt_date = st.date_input("Preferred Appointment Date")
        message = st.text_area("Message / Notes for Custodian")
        submit_appt = st.form_submit_button("Send Request to Custodian")

        if submit_appt and message.strip():
            appt_df = load_data("appointments")
            new_appt = pd.DataFrame([{
                "school_name": selected_school,
                "date": str(appt_date),
                "message": message.strip(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            appt_df = pd.concat([appt_df, new_appt], ignore_index=True)
            conn.update(worksheet="appointments", data=appt_df)
            st.success("Your request has been sent to the Custodian!")
