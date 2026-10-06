# GP 보조 Program
import os
import io
import re
import urllib.request
import streamlit as st
from google import genai
from google.genai import types
import PyPDF2
import docx

# ReportLab 관련 모듈
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# -------------------------------------------------------------
# 0. 초기화(Reset) 함수 및 세션 상태 관리
# -------------------------------------------------------------
def reset_patient_session():
    """다음 환자를 위해 모든 입력 및 생성 데이터를 초기화합니다."""
    st.session_state.ai_draft = ""
    st.session_state.final_content = ""
    st.session_state.step = 1
    # file_uploader 초기화
    st.session_state.uploader_key = st.session_state.get("uploader_key", 0) + 1
    st.rerun()

# 세션 기본값 세팅
if "ai_draft" not in st.session_state:
    st.session_state.ai_draft = ""
if "final_content" not in st.session_state:
    st.session_state.final_content = ""
if "step" not in st.session_state:
    st.session_state.step = 1
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# -------------------------------------------------------------
# 1. 안전한 PDF 생성 함수 (지연/멈춤 100% 방지)
# -------------------------------------------------------------
def get_korean_font_name():
    font_name = "NanumGothic"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name

    font_path = "NanumGothic.ttf"
    # 1. 프로젝트 폴더에 파일이 있으면 즉시 등록 (0.01초)
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            return "Helvetica"

    # 2. 파일이 없으면 웹 다운로드 시도 (최대 1.5초만 대기 후 실패 시 기본 영문폰트)
    try:
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        with urllib.request.urlopen(url, timeout=1.5) as response, open(font_path, 'wb') as out_file:
            out_file.write(response.read())
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return "Helvetica"

def generate_pdf(content_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=40,
        bottomMargin=40
    )
    
    font_family = get_korean_font_name()
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=6
    )
    
    header_style = ParagraphStyle(
        'DocHeader',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=4
    )

    story = []
    story.append(Paragraph("🩺 AI Medical Clinic - Patient Care Summary", title_style))
    story.append(Paragraph("Personalized Care Guidance & Clinical Assessment", body_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=15))
    
    lines = content_text.split('\n')
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        
        safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', safe_line)
        
        if safe_line.startswith('#') or any(safe_line.startswith(prefix) for prefix in ['1.', '2.', '3.', '📌', '🔍', '💡']):
            clean_header = safe_line.lstrip('#').strip()
            story.append(Paragraph(f"<b>{clean_header}</b>", header_style))
        else:
            story.append(Paragraph(safe_line, body_style))
            
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceAfter=8))
    disclaimer_style = ParagraphStyle('Disclaimer', parent=body_style, fontSize=8, leading=11, textColor=colors.HexColor("#718096"))
    story.append(Paragraph("<i>This document is prepared for patient education and care guidance by AI Medical Clinic. Please contact the clinic if symptoms worsen.</i>", disclaimer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# -------------------------------------------------------------
# 2. 문서 텍스트 추출 함수
# -------------------------------------------------------------
def extract_text_from_file(uploaded_file):
    text = ""
    try:
        if uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
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
# 3. Streamlit UI 및 Gemini API 설정 (안전성 강화)
# -------------------------------------------------------------
st.set_page_config(page_title="AI 어시스턴트 to GP", layout="wide")

# # API 키 명확한 검증
# api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

# API 키 명확한 우선순위 지정
selected_api_key = (
    st.secrets.get("GEMINI_API_KEY") 
    or os.getenv("GEMINI_API_KEY") 
    or os.getenv("GOOGLE_API_KEY")
)

api_key = selected_api_key

client = genai.Client(api_key=selected_api_key)

with st.sidebar:
    st.header("⚙️ 관리 도구")
    if not api_key:
        api_key = st.text_input("🔑 Gemini API Key 입력", type="password")
        if not api_key:
            st.warning("API Key가 설정되어 있지 않습니다.")
    
    st.write("---")
    st.write("새 환자가 오면 버튼을 눌러 모든 데이터를 초기화하세요.")
    if st.button("🔄 새 환자 진료 (Clear All)", use_container_width=True, type="secondary"):
        reset_patient_session()

st.title("🩺 AI 분석 및 환자 설명 시스템")

if not api_key:
    st.error("⚠️ GEMINI_API_KEY가 감지되지 않았습니다. 사이드바에 API 키를 입력하거나 .env / st.secrets를 설정해주세요.")
    st.stop()

client = genai.Client(api_key=api_key)

# -------------------------------------------------------------
# 4. 데이터 입력 섹션 (과거 기록 + 현재 상황 + 파일 업로드)
# -------------------------------------------------------------
with st.expander("📂 1단계: 환자 데이터 및 검사 결과 입력", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        pmh_data = st.text_area(
            "과거 병력 및 기본 데이터 (PMHx)", 
            height=150, 
            value="62세 남성. 기저질환: 고혈압, 제2형 당뇨."
        )
        current_data = st.text_area(
            "현재 호소 증상 및 상황 (Current Issue)", 
            height=150, 
            value="최근 2주간 극심한 피로감과 발목 부종 발생."
        )
    with col2:
        st.markdown("**검사 결과 파일 업로드 (PDF, Word, TXT)**")
        uploaded_files = st.file_uploader(
            "피검사, X-Ray, CT 판독지 등을 올려주세요.", 
            type=['pdf', 'docx', 'txt'], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )
        
        file_text_combined = ""
        if uploaded_files:
            for f in uploaded_files:
                file_text_combined += f"--- [{f.name}] 내용 ---\n"
                file_text_combined += extract_text_from_file(f) + "\n"
            st.success(f"{len(uploaded_files)}개의 파일이 로드되었습니다.")

            
            
# -------------------------------------------------------------
# 5. AI 분석 실행 (멈춤 현상 해결 버전)
# -------------------------------------------------------------
if st.button("🚀 AI 분석 및 초안 생성", type="primary"):
    with st.spinner("Gemini가 데이터를 분석하고 초안을 작성 중입니다..."):
        system_instruction = (
            "너는 호주 GP(General Practitioner)를 보조하는 임상 AI 어시스턴트야. "
            "주어진 환자 정보와 검사 결과를 바탕으로, 의사가 환자에게 직접 화면을 보여주며 "
            "이해하기 쉽게 설명할 수 있는 '환자용 요약 및 케어 가이드라인' 초안을 마크다운으로 작성해 줘."
        )
        user_prompt = f"""
[환자 데이터]
- 과거력 (PMHx): {pmh_data}
- 현재 호소 증상: {current_data}
- 검사 결과 파일 내용: {file_text_combined[:8000]}  # 텍스트가 너무 긴 경우 대비 슬라이싱

[작성 및 출력 양식]
반드시 마크다운을 사용해 아래 3가지 섹션으로 작성해 줘:
1. 📌 오늘 진료 요약 (환자가 이해하기 쉽게 3줄 요약)
2. 🔍 주요 검사 결과 (정상 vs 비정상 수치 비교 시각화)
3. 💡 향후 치료 및 주의사항 (Action Plan)
"""
        try:
            # chat 세션 생성
            chat = client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            
            # 메시지 전송
            response = chat.send_message(user_prompt)
            
            # 응답 정상 수신 확인
            if response and response.text:
                st.session_state.ai_draft = response.text
                st.session_state.final_content = response.text
                st.session_state.step = 2
                st.success("초안 생성이 완료되었습니다! 아래 2단계에서 확인하세요.")
            else:
                st.warning("Gemini에서 빈 응답이 반환되었습니다.")
                
        except Exception as e:
            st.error(f"❌ AI 분석 중 오류가 발생했습니다: {str(e)}")
            print(f"[ERROR DEBUG] AI Call Failed: {e}")  # 터미널에도 에러 출력

# -------------------------------------------------------------
# 6. 의사 검토 및 수정
# -------------------------------------------------------------
if st.session_state.step >= 2 and st.session_state.ai_draft:
    st.markdown("---")
    st.subheader("✍️ 2단계: GP 검토 및 초안 수정")
    st.info("AI가 작성한 아래 내용을 원장님의 의학적 판단에 맞게 자유롭게 수정하세요.")
    
    edited_text = st.text_area(
        "최종 설명서 초안", 
        value=st.session_state.final_content, 
        height=320
    )
    
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("✅ 수정 완료 및 3단계 확정"):
            st.session_state.final_content = edited_text
            st.session_state.step = 3
            st.rerun()

# -------------------------------------------------------------
# 7. 환자용 화면 & 저장 & 완료 후 Clear 버튼
# -------------------------------------------------------------
if st.session_state.step == 3 and st.session_state.final_content:
    st.markdown("---")
    st.subheader("🖥️ 3단계: 환자 설명용 인포그래픽 화면")
    st.caption("이 화면을 환자에게 보여주며 설명하시거나, 필요에 따라 TXT 또는 정식 PDF로 저장할 수 있습니다.")
    
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
    
    # 다운로드 버튼 영역 (TXT + PDF)
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            label="📝 TXT 파일 다운로드 (수정/보관용)",
            data=st.session_state.final_content,
            file_name="Patient_Care_Summary.txt",
            mime="text/plain",
            use_container_width=True
        )
    with col_d2:
        pdf_data = generate_pdf(st.session_state.final_content)
        st.download_button(
            label="📄 정식 PDF 다운로드 (환자 출력/전송용)",
            data=pdf_data,
            file_name="Patient_Care_Summary.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

    st.markdown("---")
    if st.button("✨ 진료 완료 및 다음 환자 맞이하기 (Clear All)", type="secondary", use_container_width=True):
        reset_patient_session()