import streamlit as st
import pdfplumber
import re
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials
from datetime import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="VTU Exam Result Portal", layout="centered")

# ---------------- HEADER ----------------
st.markdown("""
    <div style="
        background: linear-gradient(90deg, #1e1e1e, #2c2c2c);
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0px 6px 20px rgba(0,0,0,0.4);
        margin-bottom: 30px;
    ">
        <h1 style="color: #f5f5f5; font-size: 42px; letter-spacing: 2px;">
            VTU Exam Result Portal
        </h1>
        <p style="color: #cccccc; font-size: 16px;">
            Semester 2 Academic Performance Dashboard
        </p>
    </div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload VTU Semester 2 Result PDF", type=["pdf"])

# ---------------- GOOGLE SHEETS CONNECTION ----------------
def connect_to_gsheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        json.loads(st.secrets["gcp_service_account"]["json"]),
        scopes=scope
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key("1n6_KyoZAJxgzRrFluNFxF3-QQOqr3JYE_hG_dYzRGMw").sheet1
    return sheet

# ---------------- PDF EXTRACTION ----------------
def extract_data_from_pdf(pdf_file):
    text = ""

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    text = re.sub(r"\n+", " ", text)

    name_match = re.search(r"Student Name\s*:\s*([A-Z\s]+)", text)
    usn_match = re.search(r"University Seat Number\s*:\s*([A-Z0-9]+)", text)

    student_name = name_match.group(1).strip() if name_match else "Not Found"

# Remove unwanted trailing single 'S'
    if student_name.endswith(" S"):
       student_name = student_name[:-2]
    usn = usn_match.group(1).strip() if usn_match else "Not Found"

    pattern = r"(BMATE201|BPHYE202|BBEE203|BPWSK206|BKSKK207|BSFHK258|BESCK204B|BPLCK205B).*?(\d+)\s+(\d+)\s+(\d+)\s+([PF])\s+\d{4}-\d{2}-\d{2}"
    matches = re.findall(pattern, text)

    subjects = []

    for match in matches:
        subjects.append({
            "Code": match[0],
            "Internal": int(match[1]),
            "External": int(match[2]),
            "Total Marks": int(match[3]),
            "Result": match[4]
        })

    return student_name, usn, subjects

# ---------------- GRADE CALCULATION ----------------
def calculate_grade_point(marks):
    if marks >= 90:
        return 10
    elif marks >= 80:
        return 9
    elif marks >= 70:
        return 8
    elif marks >= 60:
        return 7
    elif marks >= 55:
        return 6
    elif marks >= 50:
        return 5
    elif marks >= 40:
        return 4
    else:
        return 0

# ---------------- CREDIT MAP ----------------
credit_map = {
    "BMATE201": 4,
    "BPHYE202": 4,
    "BBEE203": 3,
    "BPWSK206": 1,
    "BKSKK207": 1,
    "BSFHK258": 1,
    "BESCK204B": 3,
    "BPLCK205B": 3
}

# ---------------- MAIN LOGIC ----------------
if uploaded_file is not None:
    student_name, usn, subjects = extract_data_from_pdf(uploaded_file)

    if len(subjects) == 0:
        st.error("No subjects detected. Please upload correct Semester 2 result PDF.")
    else:
        st.markdown(f"### 👤 Student Name: **{student_name}**")
        st.markdown(f"### 🆔 USN: **{usn}**")
        st.markdown("---")

        total_credits = 0
        total_weighted_points = 0

        for sub in subjects:
            code = sub["Code"]
            total_marks = sub["Total Marks"]

            credit = credit_map.get(code, 0)
            grade_point = calculate_grade_point(total_marks)

            sub["Credit"] = credit
            sub["Grade Point"] = grade_point

            total_credits += credit
            total_weighted_points += grade_point * credit

        df = pd.DataFrame(subjects)

        st.subheader("📊 Subject Performance")
        st.dataframe(df, use_container_width=True)

        sgpa = total_weighted_points / total_credits

        st.markdown(f"""
            <div style="
                background: #f5f5f5;
                padding: 25px;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
                margin-top: 20px;
            ">
                <h2 style="color: #1e1e1e;">
                    SGPA: {round(sgpa, 2)}
                </h2>
            </div>
        """, unsafe_allow_html=True)

        # -------- SAVE / UPDATE TO SHEET --------
        try:
            sheet = connect_to_gsheet()
            records = sheet.get_all_records()

            usn_found = False

            for index, row in enumerate(records, start=2):
                if row["USN"] == usn:
                    sheet.update(f"C{index}", round(sgpa, 2))
                    sheet.update(f"E{index}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    usn_found = True
                    st.info("🔄 Existing record updated.")
                    break

            if not usn_found:
                sheet.append_row([
                    student_name,
                    usn,
                    round(sgpa, 2),
                    "Semester 2",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ])
                st.success("✅ New record added to database.")

        except Exception as e:
            st.error("❌ Could not connect to Google Sheets.")
            st.write(e)

# ---------------- TEACHER PORTAL ----------------
st.markdown("""
    <div style="
        margin-top: 60px;
        padding: 30px;
        background: linear-gradient(135deg, #2c2c2c, #1e1e1e);
        border-radius: 15px;
        text-align: center;
        box-shadow: 0px 6px 20px rgba(0,0,0,0.4);
    ">
        <h2 style="color: #f5f5f5;">
            🎓 Teacher Portal
        </h2>
        <p style="color: #cccccc;">
            Retrieve student academic record
        </p>
    </div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,2,1])

with col2:
    search_usn = st.text_input("Enter USN", key="teacher_usn")
    search_button = st.button("🔎 Search Record", use_container_width=True)

if search_button:
    with st.spinner("Searching database..."):
        try:
            sheet = connect_to_gsheet()
            data = sheet.get_all_records()

            found = False

            for row in data:
                if row["USN"] == search_usn.strip():
                    st.markdown(f"""
                        <div style="
                            background: #f5f5f5;
                            padding: 25px;
                            border-radius: 12px;
                            text-align: center;
                            box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
                            margin-top: 20px;
                        ">
                            <h3>Student Record</h3>
                            <p><strong>Name:</strong> {row['Student Name']}</p>
                            <p><strong>USN:</strong> {row['USN']}</p>
                            <p><strong>SGPA:</strong> {row['SGPA']}</p>
                        </div>
                    """, unsafe_allow_html=True)

                    found = True
                    break

            if not found:
                st.error("No record found for this USN.")

        except Exception as e:
            st.error("Could not retrieve data.")
            st.write(e)



