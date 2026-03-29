import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from fpdf import FPDF
import numpy as np
import hashlib
import plotly.express as px
import plotly.io as pio

pio.templates["custom_dark"] = pio.templates["plotly_dark"]

pio.templates["custom_dark"].layout.update({
    "paper_bgcolor": "#0f172a",
    "plot_bgcolor": "#0f172a",
    "font": {"color": "#e2e8f0"},
    "colorway": ["#38bdf8", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"]
})

pio.templates.default = "custom_dark"

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(page_title="Hospital System", layout="wide")

st.markdown("""
<style>

/* Background */
.main {
    background: linear-gradient(to right, #eef2f3, #dfe9f3);
}

/* Headings */
h1, h2, h3, h4 {
    color: #1a237e;
}

/* Cards spacing */
.block-container {
    padding-top: 2rem;
    padding-bottom: 1rem;
}

/* Plotly chart styling */
.plotly-chart {
    border-radius: 16px;
}

/* Better spacing */
section.main > div {
    padding-top: 1rem;
}

</style>
""", unsafe_allow_html=True)

# -------------------------------
# UI Styling
# -------------------------------
st.markdown("""
<style>
.main {
    background: linear-gradient(to right, #eef2f3, #dfe9f3);
}
h2, h3, h4 {
    color: #1a237e;
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
password TEXT,
role TEXT DEFAULT 'staff')''')

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
discharge_date TEXT DEFAULT '',
department TEXT,
room_charge INTEGER DEFAULT 0,
medicine_charge INTEGER DEFAULT 0
)''')

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

add_column_if_missing("users", "hospital_id", "TEXT")
add_column_if_missing("patients", "hospital_id", "TEXT")
add_column_if_missing("appointments", "hospital_id", "TEXT")
add_column_if_missing("opd", "hospital_id", "TEXT")
add_column_if_missing("patients", "phone", "TEXT DEFAULT ''")
add_column_if_missing("patients", "payment_status", "TEXT DEFAULT 'Pending'")
add_column_if_missing("patients", "status", "TEXT DEFAULT 'Admitted'")
add_column_if_missing("patients", "discharge_date", "TEXT DEFAULT ''")
add_column_if_missing("patients", "department", "TEXT")
add_column_if_missing("patients", "room_charge", "INTEGER DEFAULT 0")
add_column_if_missing("patients", "medicine_charge", "INTEGER DEFAULT 0")

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
        hospital_id = u  # simple unique mapping

        c.execute("INSERT INTO users (username, password, hospital_id) VALUES (?, ?, ?)", 
                  (u, hashed, hospital_id))
        conn.commit()
        return True
    except Exception:
        return False

def login_user(u, p):
    hashed = hash_password(p)
    c.execute("SELECT hospital_id FROM users WHERE username=? AND password=?", (u, hashed))
    return c.fetchone()
    
def add_patient(n, a, d, doc, dt, f, phone, payment_status, status):
    c.execute("""INSERT INTO patients
        (hospital_id, name, age, disease, doctor, admission_date, fees, phone, payment_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (st.session_state.hospital_id, n, a, d, doc, dt, f, phone, payment_status, status))
    conn.commit()

def view_patients():
    df = pd.read_sql_query(
        "SELECT * FROM patients WHERE hospital_id=?",
        conn,
        params=(st.session_state.hospital_id,)
    )

    # Proper column rename (UI friendly)
    df.rename(columns={
        "id": "ID",
        "name": "Name",
        "age": "Age",
        "disease": "Disease",
        "doctor": "Doctor",
        "department": "Department",
        "admission_date": "Admission Date",
        "fees": "Fees",
        "phone": "Phone",
        "payment_status": "Payment Status",
        "status": "Status",
        "discharge_date": "Discharge Date",
        "room_charge": "Room Charge",
        "medicine_charge": "Medicine Charge"
    }, inplace=True)

    return df

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
    c.execute("INSERT INTO appointments (hospital_id, patient_name, doctor, date) VALUES (?, ?, ?, ?)", 
              (st.session_state.hospital_id, n, doc, dt))
    conn.commit()

def view_appointments():
    return pd.read_sql_query(
        "SELECT * FROM appointments WHERE hospital_id=?",
        conn,
        params=(st.session_state.hospital_id,)
    )

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
            res = login_user(u, p)   # get hospital_id

            if res:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.hospital_id = res[0] 
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
    "OPD Queue",
    "Smart Insights"
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
            department = st.selectbox("Department", ["General", "Cardiology", "Orthopedic", "ICU"])
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

    st.title("📊 Hospital Analytics Dashboard")
    st.caption("Real-time insights for better hospital decisions")


    st.subheader("Hospital Dashboard")
    df = view_patients()
    full_df = df.copy() 

    if not df.empty:
        df["Admission Date"] = pd.to_datetime(df["Admission Date"], errors="coerce")
        full_df["Admission Date"] = pd.to_datetime(full_df["Admission Date"], errors="coerce")  # ⭐ ADD THIS

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

        # ==============================
        # 📈 GROWTH CALCULATION
        # ==============================

        prev_df = full_df.copy()

        if period == "Today":
            prev_df = prev_df[prev_df["Admission Date"].dt.date == (today - pd.Timedelta(days=1)).date()]

        elif period == "This Week":
            prev_df = prev_df[
                (prev_df["Admission Date"] >= today - pd.Timedelta(days=14)) &
                (prev_df["Admission Date"] < today - pd.Timedelta(days=7))
            ]

        elif period == "This Month":
            prev_month = today.month - 1 if today.month > 1 else 12
            prev_df = prev_df[prev_df["Admission Date"].dt.month == prev_month]
            
        # Search
        search = st.text_input("Search Patient by Name")
        if search:
            df = df[df["Name"].str.contains(search, case=False, na=False)]

        if df.empty:
            st.info("No data for selected period.")
            st.stop()

       
        # ==============================
        # 📊 KPI CALCULATIONS (FINAL)
        # ==============================

        total_patients = len(df)

        total_revenue = df[df["Payment Status"] == "Paid"]["Fees"].sum()

        pending_count = df[df["Payment Status"] == "Pending"].shape[0]

        admitted = df[df["Status"] == "Admitted"].shape[0]

        # ==============================
        # 🎨 KPI STYLING (PROFESSIONAL)
        # ==============================
        st.markdown("""
        <style>
        .kpi-card {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid #334155;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            transition: 0.3s;
        }
        .kpi-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.5);
        }

        .kpi-title {
            color: #94a3b8;
            font-size: 14px;
        }

        .kpi-value {
            color: #38bdf8;
            font-size: 34px;
            font-weight: bold;
            margin: 5px 0;
        }

        .kpi-sub {
            color: #64748b;
            font-size: 12px;
        }
        </style>
        """, unsafe_allow_html=True)

        
        # ==============================
        # 🧾 KPI DISPLAY
        # ==============================

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">👨‍⚕️ Total Patients</div>
                <div class="kpi-value">{total_patients}</div>
                <div class="kpi-sub">Hospital workload</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">💰 Total Revenue</div>
                <div class="kpi-value">₹{total_revenue:,}</div>
                <div class="kpi-sub">Total earnings</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">⚠️ Pending Payments</div>
                <div class="kpi-value">{pending_count}</div>
                <div class="kpi-sub">Needs attention</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">🛏️ Admitted Patients</div>
                <div class="kpi-value">{admitted}</div>
                <div class="kpi-sub">Current occupancy</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 📥 EXPORT DATA
        st.download_button(
            "📥 Download Patient Data",
            df.to_csv(index=False),
            file_name="hospital_data.csv",
            mime="text/csv"
        )

        # ==============================
        # 📊 PREMIUM CHARTS (PLOTLY)
        # ==============================

        st.markdown("""
        <style>
        .plotly-chart {
            border-radius: 12px;
        }
        </style>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 💰 Doctor Revenue")
            doc_rev = df.groupby("Doctor")["Fees"].sum().reset_index()
            doc_rev = doc_rev.sort_values(by="Fees", ascending=False)

            fig = px.bar(
                doc_rev,
                x="Doctor",
                y="Fees",
                color="Doctor",
                title="Doctor Revenue Contribution",
                color_discrete_sequence=px.colors.qualitative.Set3
            )

            fig.update_layout(
                xaxis_tickangle=-30,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### 🏥 Department Patients")
            dept = df["Department"].value_counts().reset_index()
            dept.columns = ["Department", "Patients"]

            fig2 = px.bar(
                dept,
                x="Department",
                y="Patients",
                color="Department",
                title="Department Workload",
                color_discrete_sequence=px.colors.qualitative.Bold
            )

            fig2.update_layout(
                xaxis_tickangle=-30,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig2, use_container_width=True)

        if not dept.empty:
            st.info(f"🏥 Highest load department: {dept.iloc[0]['Department']}")

        if not df.empty:
            top_doc = df.groupby("Doctor")["Fees"].sum().idxmax()
            st.success(f"💰 Top revenue generating doctor: Dr. {top_doc}")    

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🦠 Disease Analysis")
            disease_counts = df["Disease"].value_counts().reset_index()
            disease_counts.columns = ["Disease", "Count"]
            disease_counts = disease_counts.sort_values(by="Count", ascending=False)

            fig1 = px.bar(
                disease_counts,
                x="Disease",
                y="Count",
                color="Disease",
                title="Disease Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2

            )

            fig1.update_layout(xaxis_tickangle=-30,
                         plot_bgcolor="rgba(0,0,0,0)",
                         paper_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(fig1, use_container_width=True)

            if not disease_counts.empty:
                st.info(f"Most common disease: {disease_counts.iloc[0]['Disease']}")

        with col_b:
            st.subheader("👨‍⚕️ Doctor Performance")
            doc_perf = df["Doctor"].value_counts().reset_index()
            doc_perf.columns = ["Doctor", "Patients"]
            doc_perf = doc_perf.sort_values(by="Patients", ascending=False)

            fig2 = px.bar(
                doc_perf,
                x="Doctor",
                y="Patients",
                color="Doctor",
                title="Doctor Workload",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )

            fig2.update_layout(xaxis_tickangle=-30,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(fig2, use_container_width=True)

            if not doc_perf.empty:
                st.success(f"Top Doctor: Dr. {doc_perf.iloc[0]['Doctor']}")

        col_c, col_d = st.columns(2)

        with col_c:
            st.subheader("📅 Daily Admission Trend")
            daily = df["Admission Date"].value_counts().sort_index().reset_index()
            daily.columns = ["Date", "Patients"]

            fig3 = px.line(
                daily,
                x="Date",
                y="Patients",
                markers=True,
                title="Daily Patient Flow"
            )

            fig3.update_layout(xaxis_tickangle=-30,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(fig3, use_container_width=True)

            if not daily.empty:
                st.info("Track patient flow to optimize staffing")

        with col_d:
            st.subheader("💰 Revenue by Disease")
            rev = df.groupby("Disease")["Fees"].sum().sort_values(ascending=False).reset_index()

            fig4 = px.bar(
                rev,
                x="Disease",
                y="Fees",
                color="Disease",
                title="Revenue Contribution",
                color_discrete_sequence=px.colors.qualitative.Bold
            )

            fig4.update_layout(xaxis_tickangle=-30,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
            )   

            st.plotly_chart(fig4, use_container_width=True)

            if not rev.empty:
                st.warning(f"Highest revenue from: {rev.iloc[0]['Disease']}")

        # ==============================
        # 🧠 BUSINESS INSIGHTS (MAIN SELLING POINT)
        # ==============================
        st.markdown("---")
        st.subheader("📊 Smart Insights")

        if not df.empty:
            busy_doc = df["Doctor"].value_counts().idxmax()
            avg_rev = int(df["Fees"].mean())

            st.info(f"Dr. {busy_doc} is handling the most patients.")
            st.info(f"Average revenue per patient: ₹{avg_rev}")

            if pending_count > 5:
                st.error("High pending payments — risk of revenue loss.")
            else:
                st.success("Payments are under control.")



    
        # Payment status breakdown

        st.subheader("Payment Status Breakdown")

    

        pay_counts = df["Payment Status"].value_counts().reset_index()
        pay_counts.columns = ["Payment Status", "Count"]

        fig = px.bar(
            pay_counts,
            x="Payment Status",
            y="Count",
            color="Payment Status",   # 🔥 adds different colors
            title="Payment Status Breakdown"
        )

        fig.update_layout(template="plotly_dark")

        st.plotly_chart(fig)

        

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
        doc_perf = df["Doctor"].value_counts().reset_index()
        doc_perf.columns = ["Doctor", "Patients"]

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
            for index, row in doc_perf.iterrows():
                pdf.cell(200, 7, txt=f"{row['Doctor']}: {row['Patients']} patients", ln=True)
            file_path = "Hospital_Summary_Report.pdf"
            pdf.output(file_path)
            with open(file_path, "rb") as f:
                st.download_button("Click to Download", f, file_name="Hospital_Summary_Report.pdf")

        # -------------------------------
        # ADVANCED HOSPITAL ANALYTICS (NEW)
        # -------------------------------
        st.markdown("---")
        st.subheader("Advanced Hospital Insights")

        col_x, col_y = st.columns(2)

        # Doctor-wise Revenue
        with col_x:
            st.markdown("### Doctor-wise Revenue")
            doc_rev = df.groupby("Doctor")["Fees"].sum().sort_values(ascending=False)

            fig = px.bar(
                doc_rev.reset_index(),
                x="Doctor",
                y="Fees",
                color="Doctor",
                title="Doctor-wise Revenue"
            )

            st.plotly_chart(fig)

        # Department-wise Patients
        with col_y:
            if "Department" in df.columns:
                st.markdown("### Department-wise Patients")
                dept_count = df["Department"].value_counts()
                fig = px.bar(
                    dept_count.reset_index(),
                    x="Department",   # ✅ correct column
                    y="count",        # ✅ correct column
                    color="Department",
                    title="Department-wise Patients"
                )

                st.plotly_chart(fig)

        # Daily Patient Trend (clean)
        st.markdown("### Daily Patient Trend (Improved)")
        daily_trend = df.groupby(df["Admission Date"].dt.date).size()
        fig = px.line(
            daily_trend.reset_index(),
            x="Admission Date",
            y=0,
            title="Daily Patient Trend"
        )

        st.plotly_chart(fig)

        # Bed Occupancy (Simple Logic)
        st.markdown("### Bed Occupancy")

        total_beds = 50  # you can change
        admitted = len(df[df["Status"] == "Admitted"])
        occupancy_rate = (admitted / total_beds) * 100

        col1, col2 = st.columns(2)
        col1.metric("Total Beds", total_beds)
        col2.metric("Occupied Beds", admitted)

        st.progress(min(int(occupancy_rate), 100))

        if occupancy_rate > 80:
            st.error("Hospital Almost Full 🚨")
        elif occupancy_rate > 50:
            st.warning("Moderate Occupancy ⚠️")
        else:
            st.success("Beds Available ✅")   

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
elif menu == "OPD Queue":
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
                c.execute("INSERT INTO opd (hospital_id, token, name, doctor, status) VALUES (?, ?, ?, ?, ?)",
                          (st.session_state.hospital_id, token, name, doctor, "Waiting"))
                conn.commit()
                st.success(f"Token {token} issued to {name}.")
                st.rerun()
            else:
                st.warning("Please enter patient name and doctor.")

    df_opd = pd.read_sql_query(
        "SELECT * FROM opd WHERE hospital_id=?",
        conn,
        params=(st.session_state.hospital_id,)
    )

    if not df_opd.empty:
        st.markdown("#### Queue")
        st.dataframe(df_opd, use_container_width=True)

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button("Call Next Patient"):
                waiting = df_opd[df_opd["status"] == "Waiting"]
                if not waiting.empty:
                    id_ = int(waiting.iloc[0]["id"])
                    name_called = waiting.iloc[0]["name"]
                    c.execute("UPDATE opd SET status='In Progress' WHERE id=?", (id_,))
                    conn.commit()
                    st.success(f"Calling: {name_called} (Token: {waiting.iloc[0]['token']})")
                    st.rerun()
                else:
                    st.info("No patients waiting.")

        with col_b:
            if st.button("Mark Current as Done"):
                in_progress = df_opd[df_opd["status"] == "In Progress"]
                if not in_progress.empty:
                    id_ = int(in_progress.iloc[0]["id"])
                    c.execute("UPDATE opd SET status='Done' WHERE id=?", (id_,))
                    conn.commit()
                    st.success(f"{in_progress.iloc[0]['name']} marked as Done.")
                    st.rerun()
                else:
                    st.info("No patient currently in progress.")

        with col_c:
            if st.button("Clear Done Patients"):
                done = df_opd[df_opd["status"] == "Done"]
                if not done.empty:
                    c.execute("DELETE FROM opd WHERE status='Done'")
                    conn.commit()
                    st.success("Cleared all done patients from queue.")
                    st.rerun()
                else:
                    st.info("No done patients to clear.")  
                
                


        waiting_count = len(df_opd[df_opd["status"] == "Waiting"])
        if waiting_count > 10:
            st.warning(f"{waiting_count} patients waiting — long queue, consider opening another counter.")
    else:
        st.info("Queue is empty.")


# -------------------------------
# DATA SCIENCE MODULE
# -------------------------------
elif menu == "Smart Insights":
    st.subheader("Smart Hospital Insights")

    df = view_patients()
    

    if df.empty:
        st.warning("No data available for analysis.")
        st.stop()

    # Convert date
    df["Admission Date"] = pd.to_datetime(df["Admission Date"], errors="coerce")

    # -------------------------------
    # 1. PATIENT RISK PREDICTION
    # -------------------------------
    st.markdown("### Patient Risk Prediction")

    age_input = st.slider("Patient Age", 0, 100, 30)
    disease_input = st.selectbox("Disease", df["Disease"].unique())

    # Simple ML-like rule (can upgrade later)
    high_risk_diseases = ["Cancer", "Heart Disease", "Stroke"]

    if st.button("Predict Risk"):
        if age_input > 60 or disease_input in high_risk_diseases:
            st.error("High Risk Patient ⚠️")
        else:
            st.success("Low Risk Patient ✅")

    # -------------------------------
    # 2. ADVANCED ANALYTICS
    # -------------------------------
    st.markdown("### Advanced Analytics")

    col1, col2 = st.columns(2)

    with col1:
        st.write("Correlation (Age vs Fees)")
        if "Age" in df.columns and "Fees" in df.columns:
            corr = df[["Age", "Fees"]].corr()
            st.dataframe(corr)

    with col2:
        st.write("Top Revenue Disease")
        top_rev = df.groupby("Disease")["Fees"].sum().idxmax()
        st.success(f"Highest Revenue from: {top_rev}")

    # -------------------------------
    # 3. TREND FORECASTING
    # -------------------------------
    st.markdown("### Patient Trend Forecast")

    daily = df["Admission Date"].value_counts().sort_index()

    if len(daily) > 5:
        trend = int(daily.tail(5).mean())
        st.metric("Expected Patients Tomorrow", trend)

        if trend > daily.mean():
            st.warning("High Load Expected 🚨")
        else:
            st.success("Normal Load ✅")
    else:
        st.info("Not enough data for prediction")

    # -------------------------------
    # 4. SMART BUSINESS INSIGHTS
    # -------------------------------
    st.markdown("### Smart Insights")

    most_common = df["Disease"].value_counts().idxmax()
    st.info(f"Most common disease: {most_common}")

    highest_doc = df["Doctor"].value_counts().idxmax()
    st.info(f"Most busy doctor: Dr. {highest_doc}")

    avg_revenue = int(df["Fees"].mean())
    st.info(f"Average revenue per patient: Rs.{avg_revenue}")   

    st.markdown("---")
    st.subheader("📊 Smart Business Insights")

    # Busiest doctor
    busy_doc = df["Doctor"].value_counts().idxmax()
    st.info(f"Dr. {busy_doc} is handling the most patients.")

    # Revenue per patient
    avg_rev = int(df["Fees"].mean())
    st.info(f"Average revenue per patient: ₹{avg_rev}")

    # Risk signal
    pending = len(df[df["Payment Status"] == "Pending"])

    if pending > 5:
        st.error("High pending payments — revenue leakage risk.")
    else:
        st.success("Payments are under control.")
         


