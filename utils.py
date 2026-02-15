import streamlit as st
import sqlite3
import json
import io
import datetime
import google.generativeai as genai
from google.api_core import exceptions
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def load_css():
    st.markdown("""
        <style>
        .stApp { background-color: #F5F9FC; color: #000000; font-family: "Courier New", Courier, monospace; }
        .stSidebar { background-color: #EBF4FA; border-right: 2px solid #000000; }
        h1, h2, h3 { font-family: "Times New Roman", Times, serif; color: #000000; border-bottom: 2px solid #000000; }
        .metric-card { background-color: #ffffff; padding: 20px; border: 1px solid #000000; box-shadow: 4px 4px 0px #cfd8dc; margin-bottom: 20px; }
        .stoic-banner { background-color: #ffffff; border: 1px solid #000000; padding: 15px; text-align: center; margin-bottom: 30px; font-weight: bold; }
        .stButton>button { background-color: #000000; color: #ffffff; border: 1px solid #000000; border-radius: 0px; }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { background-color: #ffffff; border: 1px solid #000000; border-radius: 0px; color: #000000; }
        </style>
        """, unsafe_allow_html=True)

class AIEngine:
    def __init__(self):
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        except Exception:
            st.error("MISSING API KEY: Add GOOGLE_API_KEY to secrets.toml")
        self.primary_model = genai.GenerativeModel("gemini-2.5-flash")
        self.fallback_model = genai.GenerativeModel("gemini-2.5-flash-lite")

    def generate_content(self, prompt, config=None):
        try:
            return self.primary_model.generate_content(prompt, generation_config=config)
        except exceptions.ResourceExhausted:
            try:
                return self.fallback_model.generate_content(prompt, generation_config=config)
            except exceptions.ResourceExhausted:
                st.error("TOKEN LIMIT REACHED.")
                raise
        except Exception as e:
            raise e

@st.cache_resource
def get_db_connection():
    # check_same_thread=False is needed for Streamlit's threading model
    conn = sqlite3.connect('wso_mentor_os.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Main Client Table with all feature columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student TEXT NOT NULL,
            session_date TEXT, 
            time TEXT,
            reminder_freq TEXT DEFAULT 'None',
            type TEXT,
            strengths TEXT,
            focus TEXT,
            history TEXT,
            stories_log TEXT,
            mock_data TEXT,
            resume_text TEXT,
            is_experienced INTEGER DEFAULT 0,
            latest_resume_json TEXT,
            session_kb_text TEXT
        )
    ''')
    
    # Global Knowledge Vault
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_kb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            content TEXT
        )
    ''')
    conn.commit()

    # Self-healing: Add columns if they don't exist (for existing DBs)
    try: cursor.execute("ALTER TABLE clients ADD COLUMN session_date TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE clients ADD COLUMN reminder_freq TEXT DEFAULT 'None'")
    except: pass

    # Load initial state
    if 'client_db' not in st.session_state:
        cursor.execute("SELECT * FROM clients")
        st.session_state['client_db'] = [dict(row) for row in cursor.fetchall()]
        # Parse JSON fields
        for client in st.session_state['client_db']:
            for key in ['stories_log', 'mock_data', 'latest_resume_json']:
                if client.get(key):
                    try: client[key] = json.loads(client[key])
                    except: client[key] = {} if 'log' in key or 'json' in key else []

    if 'global_kb' not in st.session_state:
        cursor.execute("SELECT * FROM global_kb")
        st.session_state['global_kb'] = [dict(row) for row in cursor.fetchall()]

def create_pdf_report(student, tech_score, beh_score, feedback, agenda):
    """Generates a branded WSO PDF report card."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setLineWidth(2)
    c.line(50, height - 50, width - 50, height - 50)
    c.setFont("Times-Bold", 24)
    c.drawString(50, height - 40, "WSO ACADEMY | PERFORMANCE CARD")
    
    # Metadata
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 80, f"CANDIDATE: {student}")
    c.drawString(50, height - 100, f"DATE: {datetime.date.today().strftime('%B %d, %Y')}")
    
    # Scores
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 140, "SESSION SCORES:")
    c.setFillColor(colors.black)
    c.rect(50, height - 190, 200, 40, stroke=1, fill=0)
    c.setFont("Helvetica", 12)
    c.drawString(60, height - 165, f"TECHNICAL: {tech_score}/10")
    c.drawString(60, height - 180, f"BEHAVIORAL: {beh_score}/10")
    
    # Verdict
    overall = (tech_score + beh_score) / 2
    verdict = "STRONG HIRE" if overall >= 8 else "NEEDS POLISH"
    c.drawString(300, height - 170, f"VERDICT: {verdict}")

    # Feedback
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 230, "MENTOR FEEDBACK & NOTES:")
    c.setFont("Helvetica", 10)
    
    text_obj = c.beginText(50, height - 250)
    text_obj.setFont("Helvetica", 10)
    
    # Simple Text Wrapping
    feedback_lines = feedback.split('\n')
    for line in feedback_lines:
        # Basic truncation to prevent overflow
        chunk_size = 90
        for i in range(0, len(line), chunk_size):
            text_obj.textLine(line[i:i+chunk_size])
    
    c.drawText(text_obj)
    
    # Footer
    c.setFont("Times-Italic", 10)
    c.drawString(50, 50, "Wall Street Oasis Mentor OS - Confidential")
    c.save()
    buffer.seek(0)
    return buffer