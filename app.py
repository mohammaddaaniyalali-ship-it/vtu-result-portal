import streamlit as st
import pdfplumber
import re
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="VTU Exam Result Portal", layout="centered")

# ---------------- PREMIUM HEADER ----------------
st.markdown("""
    <div style="
        background: linear-gradient(90deg, #1e1e1e, #2c2c2c);
        padding: 25px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
        margin-bottom: 25px;
    ">
        <h1 style="
            color: #f5f5f5;
            font-size: 40px;
            letter-spacing: 2px;
            margin-bottom: 5px;
        ">
            VTU Exam Result Portal
        </h1>
        <p style="
            color: #dcdcdc;
            font-size: 16px;
            margin-top: 0px;
        ">
            Semester 1 Academic Performance Dashboard
        </p>
    </div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload VTU Semester 1 Result PDF", type=["pdf"])

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
    sheet = client.open("VTU_Results_Database").sheet1
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
    usn = usn_match.group(1).strip() if usn_match else "Not Found"

    pattern = r"(BMATE101|BCHEE102|BCEDK103|BENGK106|BICOK107|BIDTK158|BESCK104E|BETCK105J).*?(\d+)\s+(\d+)\s+(\d+)\s+([PF])\s+\d{4}-\d{2}-\d{2}"
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
    "BMATE101": 4,
    "BCHEE102": 4,
    "BCEDK103": 3,
    "BENGK106": 1,
    "BICOK107": 1,
    "BIDTK158": 1,
    "BESCK104E": 3,
    "BETCK105J": 3
}

# ---------------- MAIN LOGIC ----------------
if uploaded_file is not None:
    student_name, usn, subjects = extract_data_from_pdf(uploaded_file)

    if len(subjects) == 0:
        st.error("No subjects detected. Please upload correct Semester 1 result PDF.")
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

        st.markdown("---")

        st.markdown(f"""
            <div style="
                background: #f5f5f5;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0px 2px 8px rgba(0,0,0,0.1);
            ">
                <h2 style="color: #1e1e1e; margin-bottom: 0;">
                    SGPA: {round(sgpa, 2)}
                </h2>
            </div>
        """, unsafe_allow_html=True)

        # ---------------- SAVE TO GOOGLE SHEETS ----------------
        try:
            sheet = connect_to_gsheet()

            if len(sheet.get_all_values()) == 0:
                sheet.append_row(["Student Name", "USN", "SGPA"])

            existing_data = sheet.get_all_records()
            usn_list = [row["USN"] for row in existing_data]

            if usn not in usn_list:
                sheet.append_row([student_name, usn, round(sgpa, 2)])
                st.success("✅ Data successfully saved to database.")
            else:
                st.info("ℹ This USN already exists in database. Not added again.")

        except Exception as e:
            st.error("❌ Could not connect to Google Sheets.")
            st.write(e)
