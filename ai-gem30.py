#
# GP 보조 Peogram
#
import os
import streamlit as st
from google import genai
from google.genai import types
import PyPDF2
import docx

# -------------------------------------------------------------
# 1. 문서 추출 함수 (PDF, DOCX, TXT)
# -------------------------------------------------------------
def extract_text_from_file(uploaded_file):
    text = ""
    try:
        if uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.name.endswith('.txt'):
            text = uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}")
    return text

# -------------------------------------------------------------
# 2. 페이지 설정 및 세션 상태 초기화
# -------------------------------------------------------------
st.set_page_config(page_title="Dr Kang  AI 어시스턴트 Demo", layout="wide")

if "ai_draft" not in st.session_state:
    st.session_state.ai_draft = ""
if "final_content" not in st.session_state:
    st.session_state.final_content = ""
    
# Get API key - prefer GEMINI_API_KEY, fallback to GOOGLE_API_KEY
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    # Fallback for your local VS Code environment
    api_key = os.getenv("GEMINI_API_KEY")
    
client = genai.Client(api_key=api_key)

# 사이드바: API 설정
with st.sidebar:
    st.header("🔑 설정")
#    api_key = st.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.title("🩺 Dr Kang AI 분석 및 환자 설명 시스템")


# -------------------------------------------------------------
# 3. 데이터 입력 섹션 (과거 기록 + 현재 상황 + 파일)
# -------------------------------------------------------------
with st.expander("📂 1단계: 환자 데이터 및 검사 결과 입력", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        pmh_data = st.text_area("과거 병력 및 기본 데이터 (PMHx)", height=150, value="62세 남성. 기저질환: 고혈압, 제2형 당뇨.")
        current_data = st.text_area("현재 호소 증상 및 상황 (Current Issue)", height=150, value="최근 2주간 극심한 피로감과 발목 부종 발생.")
    with col2:
        st.markdown("**검사 결과 파일 업로드 (PDF, Word, TXT)**")
        uploaded_files = st.file_uploader("피검사, X-Ray, CT 판독지 등을 올려주세요.", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)
        
        file_text_combined = ""
        if uploaded_files:
            for f in uploaded_files:
                file_text_combined += f"--- [{f.name}] 내용 ---\n"
                file_text_combined += extract_text_from_file(f) + "\n"
            st.success(f"{len(uploaded_files)}개의 파일이 정상적으로 로드되었습니다.")

# -------------------------------------------------------------
# 4. AI 분석 실행
# -------------------------------------------------------------
if st.button("🚀 AI 분석 및 초안 생성", type="primary"):
    with st.spinner("데이터를 종합하여 분석 중입니다..."):
        prompt = f"""
        너는 호주 GP를 돕는 AI야. 아래 데이터를 분석해서, 의사가 환자에게 직접 모니터를 보여주며 설명할 수 있도록 '환자용 요약 및 인포그래픽 텍스트' 초안을 작성해 줘.

        [데이터]
        - 과거력: {pmh_data}
        - 현재상황: {current_data}
        - 검사파일: {file_text_combined}

        [출력 양식]
        반드시 마크다운을 사용해 아래 3가지 섹션으로 작성해.
        1. 📌 오늘 진료 요약 (환자가 이해하기 쉽게 3줄 요약)
        2. 🔍 주요 검사 결과 (정상 vs 비정상 수치 비교 시각화)
        3. 💡 향후 치료 및 주의사항 (Action Plan)
        """
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            st.session_state.ai_draft = response.text
        except Exception as e:
            st.error(f"AI API 오류: {e}")

# -------------------------------------------------------------
# 5. 의사 검토 및 수정 (Human-in-the-loop)
# -------------------------------------------------------------
if st.session_state.ai_draft:
    st.markdown("---")
    st.subheader("✍️ 2단계: GP 검토 및 초안 수정")
    st.info("AI가 작성한 아래 내용을 원장님의 의학적 판단에 맞게 자유롭게 수정하세요.")
    
    # 의사가 직접 타이핑해서 고칠 수 있는 텍스트 에리어
    edited_text = st.text_area(
        "최종 설명서 초안", 
        value=st.session_state.ai_draft, 
        height=350
    )
    
    if st.button("✅ 수정 완료 및 환자 설명 화면 띄우기"):
        st.session_state.final_content = edited_text

# -------------------------------------------------------------
# 6. 환자용 인포그래픽 시각화 및 파일 저장
# -------------------------------------------------------------
if st.session_state.final_content:
    st.markdown("---")
    st.subheader("🖥️ 3단계: 환자 설명용 인포그래픽 화면")
    st.caption("이 화면을 환자에게 보여주며 설명하시거나, 파일로 저장해 출력/전송할 수 있습니다.")
    
    # 인포그래픽 느낌을 내기 위한 CSS 스타일링 컨테이너
    st.markdown("""
    <style>
    .info-card {
        background-color: #f8fafc;
        border-left: 5px solid #2b6cb0;
        padding: 20px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<div class="info-card">{st.session_state.final_content}</div>', unsafe_allow_html=True)
    
    # TXT 파일로 저장
    st.download_button(
        label="💾 최종본 파일로 저장 (Download as TXT)",
        data=st.session_state.final_content,
        file_name="Patient_Care_Summary.txt",
        mime="text/plain",
        type="primary"
    )