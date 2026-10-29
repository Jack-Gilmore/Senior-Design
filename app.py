import streamlit as st
import pypdfium2 as pdfium
import easyocr
import numpy as np
import re

# Initialize EasyOCR reader with quantized weights for faster CPU inference
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False, quantize=True)

reader = load_ocr()

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
        with st.spinner("Processing document via Optimized Pure-Python OCR..."):
            # 1. Load PDF and render at scale=1.5 (Fast & clear balance)
            pdf = pdfium.PdfDocument(uploaded_file.read())
            
            full_text = ""
            progress_bar = st.progress(0)
            total_pages = len(pdf)

            for i, page in enumerate(pdf):
                # Render page image
                image = page.render(scale=1.5).to_pil()
                img_array = np.array(image)
                
                # 2. Optimized EasyOCR text extraction
                results = reader.readtext(
                    img_array, 
                    detail=0, 
                    paragraph=True,       # Group lines to speed up processing
                    canvas_size=1200       # Prevent massive image upscaling
                )
                full_text += " ".join(results) + "\n"
                
                # Update progress bar
                progress_bar.progress((i + 1) / total_pages)

            # 3. Regex Extraction
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