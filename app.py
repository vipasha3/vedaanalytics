import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from fpdf import FPDF
import numpy as np
import hashlib

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(page_title="Hospital System", layout="wide")

# -------------------------------
# UI Styling
# -------------------------------
st.markdown("""
<style>
.main { background-color: #f5f7fa; }
.stButton>button {
    background-color: #0066cc;
    color: white;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Database
# -------------------------------
conn = sqlite3.connect("hospital.db", check_same_thread=False)
c = conn.cursor()

# USERS
c.execute('''CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE,
password TEXT)''')

# PATIENTS — updated with phone, payment_status, status, discharge_date
c.execute('''CREATE TABLE IF NOT EXISTS patients (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
age INTEGER,
disease TEXT,
doctor TEXT,
admission_date TEXT,
fees INTEGER DEFAULT 0,
phone TEXT DEFAULT '',
payment_status TEXT DEFAULT 'Pending',
status TEXT DEFAULT 'Admitted',
discharge_date TEXT DEFAULT '')''')

# APPOINTMENTS
c.execute('''CREATE TABLE IF NOT EXISTS appointments (
id INTEGER PRIMARY KEY AUTOINCREMENT,
patient_name TEXT, doctor TEXT, date TEXT)''')

# OPD SYSTEM
c.execute('''CREATE TABLE IF NOT EXISTS opd (
id INTEGER PRIMARY KEY AUTOINCREMENT,
token INTEGER,
name TEXT,
doctor TEXT,
status TEXT)''')

conn.commit()

# Migrate existing DB: add new columns if they don't exist yet
def add_column_if_missing(table, column, col_type):
    try:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()
    except Exception:
        pass  # Column already exists

add_column_if_missing("patients", "phone", "TEXT DEFAULT ''")
add_column_if_missing("patients", "payment_status", "TEXT DEFAULT 'Pending'")
add_column_if_missing("patients", "status", "TEXT DEFAULT 'Admitted'")
add_column_if_missing("patients", "discharge_date", "TEXT DEFAULT ''")

# -------------------------------
# HELPER: Hash password
# -------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------------------
# FUNCTIONS
# -------------------------------
def add_user(u, p):
    try:
        hashed = hash_password(p)
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (u, hashed))
        conn.commit()
        return True
    except Exception:
        return False

def login_user(u, p):
    hashed = hash_password(p)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, hashed))
    return c.fetchone() is not None

def add_patient(n, a, d, doc, dt, f, phone, payment_status, status):
    c.execute("""INSERT INTO patients
        (name, age, disease, doctor, admission_date, fees, phone, payment_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (n, a, d, doc, dt, f, phone, payment_status, status))
    conn.commit()

def view_patients():
    c.execute("SELECT * FROM patients")
    rows = c.fetchall()
    if rows:
        return pd.DataFrame(rows, columns=[
            "ID", "Name", "Age", "Disease", "Doctor",
            "Admission Date", "Fees", "Phone", "Payment Status", "Status", "Discharge Date"
        ])
    return pd.DataFrame()

def discharge_patient(patient_id, discharge_dt):
    c.execute(
        "UPDATE patients SET status='Discharged', discharge_date=? WHERE id=?",
        (str(discharge_dt), patient_id)
    )
    conn.commit()

def update_payment(patient_id, payment_status):
    c.execute("UPDATE patients SET payment_status=? WHERE id=?", (payment_status, patient_id))
    conn.commit()

def add_appointment(n, doc, dt):
    c.execute("INSERT INTO appointments (patient_name, doctor, date) VALUES (?, ?, ?)", (n, doc, dt))
    conn.commit()

def view_appointments():
    c.execute("SELECT * FROM appointments")
    return pd.DataFrame(c.fetchall(), columns=["ID", "Patient", "Doctor", "Date"])

# -------------------------------
# PDF: Per-patient bill
# -------------------------------
def generate_patient_bill(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Patient Bill / Receipt", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 8, txt=f"Patient Name  : {row['Name']}", ln=True)
    pdf.cell(200, 8, txt=f"Age           : {row['Age']}", ln=True)
    pdf.cell(200, 8, txt=f"Disease       : {row['Disease']}", ln=True)
    pdf.cell(200, 8, txt=f"Doctor        : {row['Doctor']}", ln=True)
    pdf.cell(200, 8, txt=f"Phone         : {row['Phone']}", ln=True)
    pdf.cell(200, 8, txt=f"Admission Date: {row['Admission Date']}", ln=True)
    pdf.cell(200, 8, txt=f"Discharge Date: {row['Discharge Date'] or 'Not discharged yet'}", ln=True)
    pdf.cell(200, 8, txt=f"Status        : {row['Status']}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(200, 8, txt=f"Total Fees    : Rs.{row['Fees']}", ln=True)
    pdf.cell(200, 8, txt=f"Payment Status: {row['Payment Status']}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, txt="Thank you for choosing our hospital.", ln=True, align="C")
    file_path = f"bill_{row['ID']}.pdf"
    pdf.output(file_path)
    return file_path

# -------------------------------
# LOGIN SYSTEM
# -------------------------------
st.sidebar.title("Vedaa Analytics")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.logged_in:
    choice = st.sidebar.radio("Login/Register", ["Login", "Register"])

    if choice == "Register":
        st.subheader("Create Account")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Register"):
            if u and p:
                if add_user(u, p):
                    st.success("Account created! Please login.")
                else:
                    st.error("Username already exists.")
            else:
                st.warning("Please enter both username and password.")

    if choice == "Login":
        st.subheader("Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(u, p):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("Invalid username or password.")

    st.stop()

else:
    st.sidebar.success(f"Welcome, {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

# -------------------------------
# MENU
# -------------------------------
menu = st.sidebar.selectbox("Menu", [
    "Add Patient",
    "Dashboard",
    "Patient Records",
    "Upload & Analyze",
    "Appointments",
    "OPD System"
])

# -------------------------------
# ADD PATIENT
# -------------------------------
if menu == "Add Patient":
    st.subheader("Add New Patient")

    with st.form("patient_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Patient Name")
            age = st.text_input("Age")
            phone = st.text_input("Phone Number")
            disease = st.text_input("Disease / Diagnosis")

        with col2:
            doctor = st.text_input("Doctor Name")
            fees = st.number_input("Fees (Rs.)", 0, 100000)
            payment_status = st.selectbox("Payment Status", ["Pending", "Paid", "Partial"])
            status = st.selectbox("Patient Status", ["Admitted", "OPD", "Discharged"])

        d = st.date_input("Admission Date")

        submitted = st.form_submit_button("Add Patient")
        if submitted:
            if name and age:
                age_int = int(age) if age.isdigit() else 0
                add_patient(name, age_int, disease, doctor, str(d), fees, phone, payment_status, status)
                st.success(f"Patient '{name}' added successfully!")
            else:
                st.warning("Name and Age are required.")

# -------------------------------
# DASHBOARD
# -------------------------------
elif menu == "Dashboard":
    st.subheader("Dashboard")
    df = view_patients()

    if not df.empty:
        df["Admission Date"] = pd.to_datetime(df["Admission Date"], errors="coerce")

        # Date filter
        st.markdown("#### Filter by Period")
        period = st.radio("Show data for:", ["All Time", "Today", "This Week", "This Month"], horizontal=True)
        today = pd.Timestamp(date.today())

        if period == "Today":
            df = df[df["Admission Date"].dt.date == today.date()]
        elif period == "This Week":
            df = df[df["Admission Date"] >= today - pd.Timedelta(days=7)]
        elif period == "This Month":
            df = df[df["Admission Date"].dt.month == today.month]

        # Search
        search = st.text_input("Search Patient by Name")
        if search:
            df = df[df["Name"].str.contains(search, case=False, na=False)]

        if df.empty:
            st.info("No data for selected period.")
            st.stop()

        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Patients", len(df))
        col2.metric("Total Revenue", f"Rs.{df['Fees'].sum():,}")
        col3.metric("Pending Payments", len(df[df["Payment Status"] == "Pending"]))
        col4.metric("Currently Admitted", len(df[df["Status"] == "Admitted"]))

        st.markdown("---")

        # Charts
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Disease Analysis")
            st.bar_chart(df["Disease"].value_counts())

        with col_b:
            st.subheader("Doctor Performance")
            doc_perf = df["Doctor"].value_counts()
            st.bar_chart(doc_perf)
            if not doc_perf.empty:
                st.write("Top Doctor:", doc_perf.idxmax())

        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader("Daily Admission Trend")
            daily = df["Admission Date"].value_counts().sort_index()
            st.line_chart(daily)

        with col_d:
            st.subheader("Revenue by Disease")
            rev = df.groupby("Disease")["Fees"].sum().sort_values(ascending=False)
            st.bar_chart(rev)

        # Payment status breakdown
        st.subheader("Payment Status Breakdown")
        pay_counts = df["Payment Status"].value_counts()
        st.bar_chart(pay_counts)

        # Pending bills list
        pending = df[df["Payment Status"] == "Pending"][["Name", "Doctor", "Fees", "Phone"]]
        if not pending.empty:
            st.warning(f"Unpaid Bills: {len(pending)} patients owe a total of Rs.{pending['Fees'].sum():,}")
            st.dataframe(pending, use_container_width=True)

        st.markdown("---")

        # Patient Prediction (fixed — no random numbers)
        st.subheader("Patient Forecast")
        daily_counts = df["Admission Date"].value_counts().sort_index()
        if len(daily_counts) >= 3:
            last = daily_counts.tail(3).values
            weights = [1, 2, 3]
            prediction = int(np.average(last, weights=weights))
            st.metric("Expected Patients Tomorrow (weighted avg)", prediction)
            overall_avg = daily_counts.mean()
            if prediction > overall_avg:
                st.warning("High patient load expected tomorrow. Consider extra staff.")
            else:
                st.success("Normal patient load expected tomorrow.")

            st.subheader("7-Day Forecast")
            trend = daily_counts.tail(7).mean()
            cols_forecast = st.columns(7)
            for i, col in enumerate(cols_forecast, 1):
                col.metric(f"Day +{i}", int(trend))
        else:
            st.info("Need at least 3 days of data for forecasting.")

        st.markdown("---")

        # Smart Recommendations
        st.subheader("Smart Recommendations")
        df["DayName"] = df["Admission Date"].dt.day_name()
        busiest_day = df["DayName"].value_counts().idxmax()
        st.info(f"Busiest day: {busiest_day} — consider increasing staff on this day.")

        top_disease = df["Disease"].value_counts().idxmax()
        st.info(f"Most common diagnosis: {top_disease} — ensure adequate resources.")

        today_df = df[df["Admission Date"].dt.date == date.today()]
        if not today_df.empty:
            today_doc = today_df["Doctor"].value_counts()
            overload_threshold = 5
            if today_doc.max() > overload_threshold:
                st.warning(f"Dr. {today_doc.idxmax()} has {today_doc.max()} patients today — may need support.")

        st.markdown("---")

        # Summary PDF Report
        st.subheader("Generate Summary Report")
        if st.button("Download Summary PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(200, 10, txt="Hospital Analytics Report", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 8, txt=f"Total Patients: {len(df)}", ln=True)
            pdf.cell(200, 8, txt=f"Total Revenue: Rs.{df['Fees'].sum():,}", ln=True)
            pdf.cell(200, 8, txt=f"Pending Payments: {len(df[df['Payment Status']=='Pending'])}", ln=True)
            pdf.cell(200, 8, txt=f"Currently Admitted: {len(df[df['Status']=='Admitted'])}", ln=True)
            if len(daily_counts) >= 3:
                pdf.cell(200, 8, txt=f"Expected Patients Tomorrow: {prediction}", ln=True)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 8, txt="Doctor Patient Count:", ln=True)
            pdf.set_font("Arial", size=11)
            for doc, count in doc_perf.items():
                pdf.cell(200, 7, txt=f"  {doc}: {count} patients", ln=True)
            file_path = "Hospital_Summary_Report.pdf"
            pdf.output(file_path)
            with open(file_path, "rb") as f:
                st.download_button("Click to Download", f, file_name="Hospital_Summary_Report.pdf")

        st.download_button(
            "Download Patient Data as CSV",
            df.to_csv(index=False),
            file_name="patients.csv",
            mime="text/csv"
        )

    else:
        st.info("No patient data found. Add patients first.")

# -------------------------------
# PATIENT RECORDS (discharge + bill)
# -------------------------------
elif menu == "Patient Records":
    st.subheader("Patient Records")
    df = view_patients()

    if df.empty:
        st.info("No patients found.")
    else:
        search = st.text_input("Search by Name or Phone")
        if search:
            df = df[
                df["Name"].str.contains(search, case=False, na=False) |
                df["Phone"].str.contains(search, case=False, na=False)
            ]

        status_filter = st.selectbox("Filter by Status", ["All", "Admitted", "Discharged", "OPD"])
        if status_filter != "All":
            df = df[df["Status"] == status_filter]

        payment_filter = st.selectbox("Filter by Payment", ["All", "Pending", "Paid", "Partial"])
        if payment_filter != "All":
            df = df[df["Payment Status"] == payment_filter]

        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.subheader("Update Patient")

        patient_names = df["Name"].tolist()
        if patient_names:
            selected_name = st.selectbox("Select Patient", patient_names)
            selected_row = df[df["Name"] == selected_name].iloc[0]
            patient_id = int(selected_row["ID"])

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Discharge Patient**")
                discharge_dt = st.date_input("Discharge Date", value=date.today(), key="disc_date")
                if st.button("Mark as Discharged"):
                    discharge_patient(patient_id, discharge_dt)
                    st.success(f"{selected_name} discharged on {discharge_dt}.")
                    st.rerun()

            with col2:
                st.markdown("**Update Payment**")
                new_payment = st.selectbox("Payment Status", ["Pending", "Paid", "Partial"], key="pay_upd")
                if st.button("Update Payment Status"):
                    update_payment(patient_id, new_payment)
                    st.success(f"Payment updated to '{new_payment}' for {selected_name}.")
                    st.rerun()

            st.markdown("---")
            st.subheader("Generate Patient Bill")
            if st.button("Generate Bill PDF"):
                bill_path = generate_patient_bill(selected_row)
                with open(bill_path, "rb") as f:
                    st.download_button(
                        f"Download Bill for {selected_name}",
                        f,
                        file_name=f"Bill_{selected_name}.pdf"
                    )

# -------------------------------
# UPLOAD & ANALYZE
# -------------------------------
elif menu == "Upload & Analyze":
    st.subheader("Upload & Analyze Excel / CSV")
    file = st.file_uploader("Upload your file", type=["csv", "xlsx"])

    if file:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        st.success(f"Loaded {len(df)} rows and {len(df.columns)} columns.")
        st.dataframe(df.head(20), use_container_width=True)

        st.markdown("#### Basic Summary")
        st.write(df.describe())

        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        if numeric_cols:
            st.markdown("#### Chart")
            chart_col = st.selectbox("Select column to chart", numeric_cols)
            st.bar_chart(df[chart_col].value_counts())

        st.download_button(
            "Download Cleaned Data",
            df.to_csv(index=False),
            file_name="analyzed_data.csv",
            mime="text/csv"
        )

# -------------------------------
# APPOINTMENTS
# -------------------------------
elif menu == "Appointments":
    st.subheader("Appointments")

    col1, col2 = st.columns(2)
    with col1:
        n = st.text_input("Patient Name")
        d = st.text_input("Doctor Name")
        dt = st.date_input("Appointment Date")
        if st.button("Book Appointment"):
            if n and d:
                add_appointment(n, d, str(dt))
                st.success(f"Appointment booked for {n} with Dr. {d} on {dt}.")
            else:
                st.warning("Please enter patient name and doctor name.")

    with col2:
        df = view_appointments()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No appointments yet.")

# -------------------------------
# OPD SYSTEM
# -------------------------------
elif menu == "OPD System":
    st.subheader("OPD Queue System")

    c.execute("SELECT MAX(token) FROM opd")
    last = c.fetchone()[0]
    token = 1 if last is None else last + 1

    st.info(f"Next Token Number: {token}")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Patient Name")
        doctor = st.text_input("Doctor")
        if st.button("Add to Queue"):
            if name and doctor:
                c.execute("INSERT INTO opd (token, name, doctor, status) VALUES (?, ?, ?, ?)",
                          (token, name, doctor, "Waiting"))
                conn.commit()
                st.success(f"Token {token} issued to {name}.")
                st.rerun()
            else:
                st.warning("Please enter patient name and doctor.")

    df_opd = pd.read_sql_query("SELECT * FROM opd", conn)

    if not df_opd.empty:
        st.markdown("#### Queue")
        st.dataframe(df_opd, use_container_width=True)

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button("Call Next Patient"):
                waiting = df_opd[df_opd["status"] == "Waiting"]
                if not waiting.empty:
                    id_ = waiting.iloc[0]["id"]
                    c.execute("UPDATE opd SET status='In Progress' WHERE id=?", (id_,))
                    conn.commit()
                    st.success(f"Calling: {waiting.iloc[0]['name']}")
                    st.rerun()
                else:
                    st.info("No patients waiting.")

        with col_b:
            if st.button("Mark Current as Done"):
                in_progress = df_opd[df_opd["status"] == "In Progress"]
                if not in_progress.empty:
                    id_ = in_progress.iloc[0]["id"]
                    c.execute("UPDATE opd SET status='Done' WHERE id=?", (id_,))
                    conn.commit()
                    st.success(f"{in_progress.iloc[0]['name']} marked as Done.")
                    st.rerun()
                else:
                    st.info("No patient currently in progress.")

        with col_c:
            if st.button("Clear Done Patients"):
                c.execute("DELETE FROM opd WHERE status='Done'")
                conn.commit()
                st.success("Cleared all done patients from queue.")
                st.rerun()

        waiting_count = len(df_opd[df_opd["status"] == "Waiting"])
        if waiting_count > 10:
            st.warning(f"{waiting_count} patients waiting — long queue, consider opening another counter.")
    else:
        st.info("Queue is empty.")