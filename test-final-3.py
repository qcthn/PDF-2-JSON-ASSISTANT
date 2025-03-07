import streamlit as st
import pdfplumber
import json
import os
import shutil
import openai
from docx import Document
import re

# Nhập OpenAI API Key
api_key = st.text_input("🔑 Nhập OpenAI API Key:", type="password")
if not api_key:
    st.warning("Vui lòng nhập OpenAI API Key để sử dụng ứng dụng.")
    st.stop()

# Cấu hình OpenAI client
client = openai.OpenAI(api_key=api_key)
def clean_text(text):
    """Làm sạch văn bản để loại bỏ ký tự NULL và các ký tự điều khiển không hợp lệ."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # Loại bỏ ký tự điều khiển
    return text.strip()
# Hàm trích xuất văn bản từ PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += clean_text(page_text) + "\n"
    except Exception as e:
        st.error(f"Lỗi khi xử lý PDF: {e}")
        return None
    return text
def clean_json_response(response_text):
    """Làm sạch phản hồi GPT để loại bỏ các ký tự không mong muốn trước khi phân tích JSON."""
    response_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', response_text)
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    return response_text.strip()
# Hàm gọi GPT để trích xuất thông tin
def extract_info_with_gpt(text):
    prompt = f"""
    Trích xuất thông tin từ văn bản CV và trả về JSON hợp lệ:
    {{
        "Name": "",
        "Email": "",
        "Phone": "",
        "Skills": [],  
        "Experience": [],  
        "Education": [],  
        "Certifications": [],  
        "Languages": [],  
        "Strengths": [],  
        "Weaknesses": [],  
        "Additional information": []
    }}
    For the **Languages** field, include:
    - The candidate's native language based on their nationality (e.g., Vietnamese for a candidate from Vietnam).
    - Any foreign language certifications (e.g., TOEIC score) and the corresponding language proficiency level (e.g., English with a proficiency level based on the score).

    For **Strengths and Weaknesses**, analyze the candidate's work experience to identify:
    - **Strengths:** Key skills and attributes demonstrated through their experience.
    - **Weaknesses:** Areas for improvement or challenges faced in their roles.
    CV text:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an expert in extracting information from CVs (resumes) and images with 10 years of experience in getting the exact information needed to recruit suitable positions for the company."

            "**Context:** I will provide you with resumes of candidates (which can be one or more) or image files containing text."

            "**Your task** is to extract information from the resumes and images I provide (I have taken the text from the resume, and the image will be provided to you below) and return the output as a JSON file."

            "Some of the most important information required for each candidate includes:"
            "- Name"
            "- Email"
            "- Phone number"
            "- Skills"
            "- Experience (including: position, timeline, responsibilities)"
            "- Education (including: degree, institution, timeline, GPA)"
            "- Certifications"
            "- Languages (including proficiency based on nationality and language certifications)"
            "- Strengths (based on the candidate's experience and job description)"
            "- Weaknesses (based on the candidate's experience and job description)"
            "- Additional information (including identification and visa details if provided)"

            "**Task:** Extract the following information from the CV text and return it as JSON."

            "**Output:** JSON file format"

            "***Note:** I can provide you with the text, but in that text will be a synthesis of many resumes of different candidates.*"

            "**REMEMBER:** The output should only be in JSON format." },
            {"role": "user", "content": prompt}
        ]
    )
    # return json.loads(response.choices[0].message.content.strip())
    extracted_text = response.choices[0].message.content.strip()
    cleaned_text = clean_json_response(extracted_text)
    # return json.loads(response.choices[0].message.content.strip())
    return json.loads(cleaned_text)
# Lưu JSON
def save_to_json(data_list, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)

# Tạo file Word
def create_word_file(text_list, output_path):
    try:
        doc = Document()
        for idx, (filename, text) in enumerate(text_list):
            doc.add_heading(f"File {idx + 1}: {filename}", level=1)
            doc.add_paragraph(clean_text(text))
            doc.add_page_break()
        doc.save(output_path)
        return True
    except Exception as e:
        st.error(f"Lỗi khi tạo file Word: {e}")
        return False

# Ứng dụng Streamlit
st.title("📄 PDF to JSON & AI Assistant")
st.write("🔹 Tải lên CV (PDF), trích xuất nội dung và đặt câu hỏi với trợ lý ảo!")

uploaded_files = st.file_uploader("📤 Chọn file PDF", type=["pdf"], accept_multiple_files=True)
temp_dir = "temp"
os.makedirs(temp_dir, exist_ok=True)

if uploaded_files:
    extracted_data = {}
    extracted_texts = {}

    for uploaded_file in uploaded_files:
        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        text = extract_text_from_pdf(temp_file_path)
        if text:
            extracted_texts[uploaded_file.name] = text
            extracted_info = extract_info_with_gpt(text)
            extracted_info["Filename"] = uploaded_file.name
            extracted_data[uploaded_file.name] = extracted_info
        os.remove(temp_file_path)

    # Tạo file Word và JSON
    word_output = os.path.join(temp_dir, "extracted_texts.docx")
    if create_word_file(list(extracted_texts.items()), word_output):
        with open(word_output, "rb") as file:
            st.download_button("📥 Tải file Word", file, file_name="extracted_texts.docx")

    json_output = os.path.join(temp_dir, "extracted_data.json")
    save_to_json(list(extracted_data.values()), json_output)
    with open(json_output, "rb") as file:
        st.download_button("📥 Tải file JSON", file, file_name="extracted_data.json")

    # Chatbot với trợ lý ảo
    st.subheader("💬 Chat với trợ lý ảo về nội dung CV")

    if len(uploaded_files) > 1:
        selected_cv = st.selectbox("Chọn CV để tương tác:", list(extracted_texts.keys()))
    else:
        selected_cv = list(extracted_texts.keys())[0]
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-3.5-turbo"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-3.5-turbo"
    text_CV = f"Dưới đây là nội dung CV của ứng viên:\n{extracted_texts[selected_cv]}"
    prompt = st.chat_input("Hỏi trợ lý ảo về CV này:")
    if prompt:
         # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[{"role": "system", "content": "Play the role of a professional HR, with 10 years of experience in finding potential candidates suitable for the company based on the CV (resume) they send Context: I will provide you with information of each CV (resume) in text form, from which I will ask you some questions related to the CV (resume) of this candidate Task: Please provide the most accurate and closest information to the question I asked, helping me have the most objective view of this candidate so that I can decide whether to hire him or not Tone: solemn, dignified, straightforward, suitable for the office environment, recruitment. Below is the content of the candidate's CV"  + extracted_texts[selected_cv] },
                {"role": "user", "content": prompt}],
                stream=True,
            )
                # if hasattr(response.choices[0].delta, "content"):    
            response = st.write_stream(stream)
        st.session_state.messages.append({"role": "assistant", "content": response})
    shutil.rmtree(temp_dir, ignore_errors=True)
