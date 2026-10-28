import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import re

# 1. Offline Session Login Wall
def check_password():
    def password_entered():
        if st.session_state["username"] == "admin" and st.session_state["password"] == "miras2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 MIRAS Secure Terminal")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        st.title("🔒 MIRAS Secure Terminal")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("Access Denied: Invalid credentials.")
        return False
        
    return True

# 2. Main Extraction Pipeline
if check_password():
    st.sidebar.success("Logged in as: Admin")
    if st.sidebar.button("Log Out"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.title("MIRAS: Multi-Metric Offline Extractor")
    st.write("Upload an infrastructure PDF report to process full-document metrics.")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file is not None:
        with st.spinner("Processing document via Air-Gapped OCR..."):
            images = convert_from_bytes(uploaded_file.read())
            
            full_text = ""
            for image in images:
                full_text += pytesseract.image_to_string(image) + "\n"
            
            metrics_schema = {
                "Generator Capacity": r"(?i)(?:generator\s+capacity|generator\s+units?|generator\s+rating|generator\s+output)\s*[:\-]?\s*([\d\.,]+\s*k?W)",
                "Fuel Reserves": r"(?i)(?:fuel\s+reserves|diesel\s+storage|fuel\s+capacity)\s*[:\-]?\s*([\d\.,]+\s*(?:gallons|days|gal))",
                "Solar/PV Output": r"(?i)(?:solar\s+capacity|pv\s+output|photovoltaic)\s*[:\-]?\s*([\d\.,]+\s*k?W)",
                "Microgrid Readiness": r"(?i)(?:microgrid\s+status|islanding\s+capability)\s*[:\-]?\s*([A-Za-z0-9\s]+)"
            }
            
            extracted_data = {}
            for metric_name, pattern in metrics_schema.items():
                matches = re.findall(pattern, full_text)
                if matches:
                    extracted_data[metric_name] = [m.strip() for m in matches]
                else:
                    extracted_data[metric_name] = "DATA_MISSING"

            st.subheader("Extracted Metrics Schema (JSON Output)")
            st.json(extracted_data)
            
            missing_count = sum(1 for v in extracted_data.values() if v == "DATA_MISSING")
            completeness_ratio = (len(extracted_data) - missing_count) / len(extracted_data)
            st.metric(label="Document Completeness Ratio", value=f"{completeness_ratio * 100:.1f}%")

            with st.expander("View Raw OCR Text"):
                st.text(full_text)