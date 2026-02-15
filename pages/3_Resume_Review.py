import streamlit as st
import utils
import re
import json
import io
import datetime
from docxtpl import DocxTemplate

st.set_page_config(page_title="Resume Engine | WSO OS", layout="wide")
utils.load_css()
utils.init_db()

st.title("WSO RESUME ENGINE")

# --- 1. CLIENT SELECTION ---
client_names = [c['student'] for c in st.session_state['client_db']]
if not client_names:
    st.warning("No clients in database. Go to Intake first.")
    st.stop()

selected_client_name = st.selectbox("SELECT CANDIDATE FROM DATABASE", client_names)
client_data = next((c for c in st.session_state['client_db'] if c['student'] == selected_client_name), None)
resume_text = client_data.get('resume_text', "")
is_experienced = client_data.get('is_experienced', 0) == 1

if not resume_text:
    st.error("⚠️ NO RESUME TEXT FOUND. Please update client dossier.")
else:
    st.success(f"✅ LOADED DOSSIER: {selected_client_name} | TRACK: {'EXPERIENCED' if is_experienced else 'UNDERGRAD'}")

st.markdown("---")

# --- WORKFLOW SELECTOR ---
review_stage = st.radio("SELECT REVIEW STAGE", ["STAGE 1: INITIAL AUDIT & QUESTIONS", "STAGE 2: REDRAFT (WITH CLIENT INPUT)"], horizontal=True)
st.markdown("---")

# Store AI output in session state so it doesn't vanish on reload
if 'ai_output_cache' not in st.session_state:
    st.session_state['ai_output_cache'] = ""

# =========================================================
# STAGE 1: INITIAL AUDIT
# =========================================================
if review_stage == "STAGE 1: INITIAL AUDIT & QUESTIONS":
    st.info("GOAL: GENERATE CLARIFYING QUESTIONS BASED ON RAW CV.")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.expander("📄 VIEW RAW CV CONTENT (FROM DB)"):
            st.text(resume_text)
    with c2:
        with st.expander("🔍 VIEW WEAK LANGUAGE HIGHLIGHTS", expanded=True):
            forbidden = ["responsible for", "assisted with", "helped", "worked on"]
            highlighted = resume_text
            for w in forbidden:
                pattern = re.compile(re.escape(w), re.IGNORECASE)
                highlighted = pattern.sub(f'<span style="background-color:#ffcccc;color:#900;">{w}</span>', highlighted)
            st.markdown(highlighted.replace('\n', '<br>'), unsafe_allow_html=True)

    st.markdown("---")
    
    if st.button("🤖 GENERATE QUESTIONNAIRE DRAFT", use_container_width=True):
        with st.spinner("Analyzing..."):
            try:
                model = utils.AIEngine()
                prompt = f"""
                You are a strict Head Mentor at Wall Street Oasis. Write a direct email to {selected_client_name}.
                CV CONTENT: {resume_text}
                Task: Ask clarifying questions to quantify results for each bullet point using WSO best practices.
                """
                response = model.generate_content(prompt)
                st.session_state['ai_output_cache'] = response.text
            except Exception as e: st.error(f"AI Error: {e}")

    # Display Generated Content (Persistent)
    if st.session_state['ai_output_cache']:
        st.subheader("GENERATED QUESTIONS (CONTEXT FOR LOGGING)")
        st.text_area("AI Output", value=st.session_state['ai_output_cache'], height=400)

# =========================================================
# STAGE 2: REDRAFT
# =========================================================
elif review_stage == "STAGE 2: REDRAFT (WITH CLIENT INPUT)":
    st.info(f"GOAL: REDRAFT RESUME FOR {selected_client_name}.")
    
    template_file = "WSO Academy Resume Template - Deal Experience.docx" if is_experienced else "WSO Academy Resume Template.docx"
    
    c1, c2 = st.columns([1, 1])
    with c1:
        client_response = st.text_area("PASTE CLIENT RESPONSES HERE:", height=300)
    with c2:
        if st.button("GENERATE & SAVE WORD DOC"):
            if not client_response: st.error("Need client responses.")
            else:
                with st.spinner("Redrafting..."):
                    try:
                        model = utils.AIEngine()
                        prompt = f"""
                        Redraft this CV into WSO JSON format.
                        CV: {resume_text}
                        Updates: {client_response}
                        Return JSON with keys: education_section, experience_section, leadership_section, additional_section.
                        """
                        response = model.generate_content(prompt, config={"response_mime_type": "application/json"})
                        data = json.loads(response.text)
                        
                        # Save to Vault
                        conn = utils.get_db_connection()
                        conn.cursor().execute("UPDATE clients SET latest_resume_json = ? WHERE student = ?", (json.dumps(data), selected_client_name))
                        conn.commit()
                        
                        # Cache text for logging
                        st.session_state['ai_output_cache'] = "Redraft Generated & Saved to Vault."
                        
                        # Render Download
                        doc = DocxTemplate(template_file)
                        doc.render(data)
                        bio = io.BytesIO()
                        doc.save(bio)
                        st.download_button("⬇️ DOWNLOAD RESUME", bio.getvalue(), f"{selected_client_name}_WSO_Resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    except Exception as e: st.error(f"Error: {e}")

# =========================================================
# 📝 LOGGING SECTION (NEW FEATURE)
# =========================================================
st.markdown("---")
st.markdown("### 📝 LOG SESSION & CONTEXT")
st.caption("Save the AI's output and your feedback to the client's history so you don't lose context.")

with st.container(border=True):
    lc1, lc2 = st.columns([1, 3])
    with lc1:
        resume_score = st.slider("CURRENT RESUME RATING", 1, 10, 5)
    with lc2:
        feedback_notes = st.text_area("MENTOR FEEDBACK / NOTES", height=100, placeholder="e.g., Weak verbs in the PE experience section.")

    if st.button("💾 SAVE SESSION TO HISTORY", type="primary", use_container_width=True):
        timestamp = datetime.date.today().strftime("%m/%d")
        
        # Capture AI Context (The questions asked or redraft status)
        context_to_save = st.session_state.get('ai_output_cache', 'No AI generation this session.')
        
        # Create detailed log entry
        log_entry = f"""
        | {timestamp}: Resume Review (Score: {resume_score}/10)
        | NOTES: {feedback_notes}
        | AI CONTEXT/QUESTIONS ASKED: {context_to_save[:500]}... [Truncated for DB]
        """
        # Clean up newlines for the 'pipe' format
        log_entry_clean = " ".join(log_entry.split())

        conn = utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT history FROM clients WHERE student = ?", (selected_client_name,))
        row = cursor.fetchone()
        
        if row:
            new_hist = (row['history'] or "") + " | " + log_entry_clean
            cursor.execute("UPDATE clients SET history = ? WHERE student = ?", (new_hist, selected_client_name))
            conn.commit()
            
            # Sync Session State
            for c in st.session_state['client_db']:
                if c['student'] == selected_client_name:
                    c['history'] = new_hist
                    break
            
            st.success("✅ Session Logged. Context saved for future reference.")
