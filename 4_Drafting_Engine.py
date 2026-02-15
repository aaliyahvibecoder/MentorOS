import streamlit as st
import utils
import datetime
import json

st.set_page_config(page_title="AI Drafter | WSO OS", layout="wide")
utils.load_css()
utils.init_db()

st.title("AI COMMUNICATIONS ARRAY")
st.info("GENERATE ASYNC FOLLOW-UPS")

# --- 1. INPUT CONFIGURATION ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### TARGET")
    client_names = [c['student'] for c in st.session_state['client_db']]
    target_client = st.selectbox("RECIPIENT", ["Generic / Prospective"] + client_names)
    
    st.markdown("### CONTEXT")
    comm_type = st.selectbox("MESSAGE TYPE", [
        "Post-Session Recap (General)",
        "Resume Review Feedback (48hr Rule)",
        "Mock Interview Results (Pass)",
        "Mock Interview Results (Fail)",
        "Networking: Cold Email Template",
        "Networking: 'Ghosted' Follow-up"
    ])
    
    platform = st.radio("PLATFORM", ["Email (Formal)", "Slack (Brief)"])

with col2:
    st.markdown("### CUSTOMIZATION")
    key_points = st.text_area("KEY POINTS / FEEDBACK (BULLET STYLE)", height=200, 
        placeholder="- Tech answers were weak on DCF\n- Great energy\n- Fix resume formatting (Education section)")

st.markdown("---")

# --- 2. THE PROMPT ENGINE ---
def get_gemini_draft(client, c_type, plat, points):
    
    # Dynamic Rule Injection based on context
    context_rules = ""
    if "Resume" in c_type:
        context_rules = "- Enforce a strict 48-hour turnaround requirement for their revisions. Remind them the total process takes 7-10 days.\n- Remind them to remove GPA if < 3.0 unless Major GPA is > 3.2.\n- Ensure no Objective statements are allowed."
    elif "Networking" in c_type:
        context_rules = "- Ensure the draft establishes common ground, proposes specific times, and is concise."
    elif "Mock Interview" in c_type:
        context_rules = "- Structure feedback into 'Technical' and 'Behavioral' sections. Mention scores on a 1-10 scale."

    system_instruction = f"""
    You are a Head Mentor at Wall Street Oasis Academy. 
    Your Vibe: Professional, minimalist, old-school Wall Street (Bloomberg Terminal style). Direct and high information density.
    
    BUSINESS RULES TO ENFORCE FOR THIS TASK:
    {context_rules}
    
    CURRENT TASK:
    Draft a {plat} message to a student named {client}.
    Context: {c_type}
    
    Specific Feedback Points to Include:
    {points}
    
    FORMATTING:
    - If Platform is 'Email (Formal)': Use Subject Line. Professional salutation. Concise paragraphs.
    - If Platform is 'Slack (Brief)': No subject. Use @{client}. Bullet points only. Very short.
    - Do NOT use emojis unless strictly necessary for tone (but generally avoid).
    - You must respond strictly with a valid JSON object containing exactly two keys: "subject" and "body". Do not wrap in markdown block.
    """

    with st.spinner("CONTACTING NEURAL ENGINE..."):
        try:
            # Initialize Robust AI Engine
            engine = utils.AIEngine()
            
            response = engine.generate_content(
                system_instruction,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text) 
        except Exception as e:
            return {"subject": "ERROR", "body": f"AI Generation Failed: {str(e)}"}

# --- 3. EXECUTION ---
if st.button("GENERATE AI DRAFT"):
    if not key_points:
        st.warning("ENTER KEY POINTS TO GUIDE THE AI.")
    else:
        # Call Gemini
        result = get_gemini_draft(target_client, comm_type, platform, key_points)
        
        # Display Output
        if platform == "Email (Formal)":
            st.text_input("SUBJECT LINE", value=result.get("subject", ""))
        
        st.text_area("MESSAGE BODY", value=result.get("body", ""), height=350)
        
        # Clipboard Helper
        st.caption("Copy raw text below:")
        st.code(result.get("body", ""), language="markdown")