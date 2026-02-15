import streamlit as st
import utils
import json
import pandas as pd
import altair as alt
import datetime
import calendar
import io
from docxtpl import DocxTemplate
from pypdf import PdfReader
import docx

# --- INITIALIZATION ---
st.set_page_config(page_title="WSO Mentor OS", layout="wide", initial_sidebar_state="expanded")
utils.load_css()
utils.init_db()

# --- HELPER: QUICK SCHEDULE UPDATE ---
def update_session_time(client_id, new_date, new_time):
    """Updates only the date/time for a specific client ID from the calendar."""
    try:
        conn = utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET session_date = ?, time = ? WHERE id = ?", (new_date, new_time, client_id))
        conn.commit()
        
        # Update Session State instantly
        for c in st.session_state['client_db']:
            if c['id'] == client_id:
                c['session_date'] = new_date
                c['time'] = new_time
                break
        st.toast("✅ Schedule Updated!")
        st.rerun()
    except Exception as e:
        st.error(f"Update failed: {e}")

# --- HELPER: CALENDAR ENGINE ---
def get_session_style(session_type):
    if "Mock" in session_type: return "🔴", "Mock Interview"
    if "Resume" in session_type: return "🔵", "Resume Review"
    if "Roadmap" in session_type: return "🟢", "Career Roadmap"
    if "Stories" in session_type: return "🟠", "7 Stories"
    if "LinkedIn" in session_type: return "🔵", "LinkedIn"
    if "Networking" in session_type: return "🟣", "Networking"
    return "⚪", "General"

def render_compact_calendar(client_db):
    if 'cal_year' not in st.session_state:
        st.session_state['cal_year'] = datetime.date.today().year
    if 'cal_month' not in st.session_state:
        st.session_state['cal_month'] = datetime.date.today().month

    # Navigation
    c_prev, c_month, c_next, c_legend = st.columns([0.5, 2, 0.5, 4])
    with c_prev:
        if st.button("◀", key="cal_prev", use_container_width=True):
            st.session_state['cal_month'] -= 1
            if st.session_state['cal_month'] == 0:
                st.session_state['cal_month'] = 12
                st.session_state['cal_year'] -= 1
            st.rerun()
    with c_next:
        if st.button("▶", key="cal_next", use_container_width=True):
            st.session_state['cal_month'] += 1
            if st.session_state['cal_month'] == 13:
                st.session_state['cal_month'] = 1
                st.session_state['cal_year'] += 1
            st.rerun()
    with c_month:
        month_name = calendar.month_name[st.session_state['cal_month']]
        st.markdown(f"#### {month_name} {st.session_state['cal_year']}")
    with c_legend:
        st.caption("🔴 Mock | 🔵 Resume | 🟢 Roadmap | 🟠 Stories | 🟣 Network")

    # Grid
    cal = calendar.monthcalendar(st.session_state['cal_year'], st.session_state['cal_month'])
    today = datetime.date.today()
    
    cols = st.columns(7)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for idx, day in enumerate(days):
        cols[idx].markdown(f"<div style='text-align:center; font-size:0.8em; font-weight:bold; color:#666;'>{day}</div>", unsafe_allow_html=True)

    for week in cal:
        cols = st.columns(7)
        for idx, day in enumerate(week):
            with cols[idx]:
                if day != 0:
                    current_date_obj = datetime.date(st.session_state['cal_year'], st.session_state['cal_month'], day)
                    current_date_str = current_date_obj.strftime("%Y-%m-%d")
                    is_today = (current_date_obj == today)
                    
                    day_sessions = [c for c in client_db if c.get('session_date') == current_date_str]
                    
                    with st.container():
                        num_style = "font-weight:bold; color:#000;" if day_sessions else "color:#aaa;"
                        if is_today: num_style += "text-decoration: underline;"
                        st.markdown(f"<div style='text-align:right; font-size:0.9em; {num_style} margin-bottom:2px;'>{day}</div>", unsafe_allow_html=True)
                        
                        for sess in day_sessions:
                            icon, _ = get_session_style(sess['type'])
                            
                            # POPOVER WITH QUICK EDIT FORM
                            with st.popover(f"{icon} {sess.get('time', '')}", use_container_width=True):
                                st.markdown(f"**{sess['student']}**")
                                st.caption(sess['type'])
                                
                                with st.form(key=f"q_edit_{sess['id']}"):
                                    # Parse existing time
                                    try:
                                        curr_time = datetime.datetime.strptime(sess.get('time', '09:00'), "%H:%M").time()
                                    except: curr_time = datetime.time(9,0)
                                    
                                    new_d = st.date_input("Date", value=current_date_obj)
                                    new_t = st.time_input("Time", value=curr_time)
                                    
                                    if st.form_submit_button("Update Slot"):
                                        update_session_time(sess['id'], new_d.strftime("%Y-%m-%d"), new_t.strftime("%H:%M"))

# --- MAIN APP LOGIC ---

client_db = st.session_state.get('client_db', [])
pending_resumes = [c for c in client_db if c.get('type') == "Resume Review (Full)" and not c.get('latest_resume_json')]
pending_count = len(pending_resumes)

# --- SIDEBAR ---
st.sidebar.markdown("## WSO MENTOR OS")
st.sidebar.info("NAVIGATE USING THE MENU ABOVE")
st.sidebar.markdown("---")
st.sidebar.metric("TOTAL CLIENTS", len(client_db)) 

# --- BANNER ---
st.markdown('<div class="stoic-banner">"NOT EVERYDAY WILL BE AWESOME, SHOW UP ANYWAY"</div>', unsafe_allow_html=True)

# --- CALENDAR WIDGET ---
render_compact_calendar(client_db)
st.markdown("---")

# --- EXECUTIVE SUMMARY ---
st.title("EXECUTIVE BRIEFING")
col1, col2 = st.columns(2)
col1.metric("ACTIVE CLIENTS", str(len(client_db)))
col2.metric("PENDING RESUME DRAFTS", str(pending_count)) 
st.markdown("---")

# --- DATABASE CRUD HELPERS ---
def delete_client(student_name):
    try:
        conn = utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE student = ?", (student_name,))
        conn.commit()
        st.session_state['client_db'] = [c for c in st.session_state['client_db'] if c['student'] != student_name]
        st.toast(f"🗑️ DELETED: {student_name}")
        st.rerun()
    except Exception as e: st.error(f"Deletion Failed: {e}")

def update_client_details(original_name, new_name, new_date, new_time, new_reminder, new_type, new_str, new_foc, new_exp, new_resume_text):
    try:
        conn = utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE clients SET student=?, session_date=?, time=?, reminder_freq=?, type=?, strengths=?, focus=?, is_experienced=?, resume_text=? WHERE student=?''', 
                       (new_name, new_date, new_time, new_reminder, new_type, new_str, new_foc, new_exp, new_resume_text, original_name))
        conn.commit()
        for client in st.session_state['client_db']:
            if client['student'] == original_name:
                client['student'] = new_name; client['session_date'] = new_date; client['time'] = new_time; client['reminder_freq'] = new_reminder
                client['type'] = new_type; client['strengths'] = new_str; client['focus'] = new_foc
                client['is_experienced'] = new_exp; client['resume_text'] = new_resume_text
                break
        st.success(f"✅ UPDATED: {new_name}")
        st.rerun()
    except Exception as e: st.error(f"Update Failed: {e}")

# --- DASHBOARD TABS ---
tab1, tab2, tab3 = st.tabs(["📋 ACTIVE DOSSIERS", "📊 ANALYTICS", "🗄️ MASTER DATABASE & VAULT"])

# TAB 1: ACTIVE DOSSIERS
with tab1:
    if not client_db: st.info("No active clients. Go to Intake.")
    for i, session in enumerate(client_db):
        st.markdown(f"""
        <div class="metric-card">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #000; padding-bottom:10px; margin-bottom:10px;">
                <span style="font-weight:bold; font-size: 1.2em;">{session.get('session_date', 'N/A')} @ {session.get('time', 'N/A')}</span>
                <span style="font-weight:bold; font-size: 1.2em;">{session.get('student', 'UNKNOWN')}</span>
            </div>
            <div><span style="font-weight:bold;">TRACK:</span> {session.get('type', 'N/A')}</div>
        </div>""", unsafe_allow_html=True)

        with st.expander(f"📂 OPEN DOSSIER: {session.get('student')}"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### 📜 HISTORY LOG")
                history_raw = session.get('history') or ""
                history_items = [h for h in history_raw.split('|') if h.strip()]
                if history_items:
                    for idx, item in enumerate(history_items):
                        preview = item[:60].replace("\n", " ") + "..." if len(item) > 60 else item
                        # SCROLLABLE POPOVER
                        with st.popover(f"📝 {preview}", use_container_width=True):
                            st.markdown("**FULL SESSION LOG:**")
                            st.text_area("Full Content", value=item.strip(), height=400, disabled=True, key=f"hist_{i}_{idx}")
                else: st.caption("No history.")

            with c2:
                if session.get('latest_resume_json'):
                    is_exp = session.get('is_experienced', 0) == 1
                    template = "WSO Academy Resume Template - Deal Experience.docx" if is_exp else "WSO Academy Resume Template.docx"
                    try:
                        doc = DocxTemplate(template); doc.render(session['latest_resume_json']); bio = io.BytesIO(); doc.save(bio)
                        st.download_button("📄 DOWNLOAD LATEST DRAFT", bio.getvalue(), f"WSO_Draft_{session.get('student')}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_btn_{i}", type="primary")
                    except: st.warning("Template missing.")
                else: st.info("No final draft.")

            st.markdown("---")
            ec1, ec2 = st.columns(2)
            if ec1.button(f"🗑️ DELETE", key=f"del_{i}"): delete_client(session.get('student'))
            
            with ec2.popover("✏️ EDIT DETAILS"):
                with st.form(key=f"edit_form_{i}"):
                    new_name = st.text_input("Name", value=session.get('student'))
                    
                    sc1, sc2, sc3 = st.columns(3)
                    try: def_date = datetime.datetime.strptime(session.get('session_date'), "%Y-%m-%d").date()
                    except: def_date = datetime.date.today()
                    try: def_time = datetime.datetime.strptime(session.get('time'), "%H:%M").time()
                    except: def_time = datetime.time(9, 0)
                    rem_opts = ["None", "24h Before", "1h Before"]
                    try: rem_idx = rem_opts.index(session.get('reminder_freq', 'None'))
                    except: rem_idx = 0
                    
                    with sc1: new_date = st.date_input("Date", value=def_date)
                    with sc2: new_time = st.time_input("Time", value=def_time)
                    with sc3: new_reminder = st.selectbox("Reminder", rem_opts, index=rem_idx)

                    type_opts = ["Mock Interview", "Career Roadmap", "7 Stories Review", "Resume Review (Full)", "LinkedIn Audit", "Networking Strategy"]
                    try: curr_idx = type_opts.index(session.get('type'))
                    except: curr_idx = 0
                    new_type = st.selectbox("Type", type_opts, index=curr_idx)
                    new_str = st.text_area("Strengths", value=session.get('strengths'))
                    new_foc = st.text_area("Focus", value=session.get('focus'))
                    new_is_exp = st.checkbox("Experienced?", value=bool(session.get('is_experienced')))
                    
                    if st.form_submit_button("SAVE CHANGES"):
                        update_client_details(session.get('student'), new_name, new_date.strftime("%Y-%m-%d"), new_time.strftime("%H:%M"), new_reminder, new_type, new_str, new_foc, 1 if new_is_exp else 0, session.get('resume_text'))

# TAB 2: ANALYTICS
with tab2:
    if client_db:
        df = pd.DataFrame(client_db)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### BUSINESS MIX")
            if 'type' in df.columns: st.bar_chart(df['type'].value_counts(), color="#000000")
        with c2:
            st.markdown("#### MOCK PERFORMANCE")
            pts = []
            for c in client_db:
                if isinstance(c.get('mock_data'), list):
                    for m in c['mock_data']: pts.append({"Student": c['student'], "Technical": m['tech'], "Behavioral": m['beh']})
            if pts:
                chart = alt.Chart(pd.DataFrame(pts)).mark_circle(size=100).encode(x=alt.X('Technical', scale=alt.Scale(domain=[0, 10])), y=alt.Y('Behavioral', scale=alt.Scale(domain=[0, 10])), color=alt.Color('Student', legend=None), tooltip=['Student', 'Technical', 'Behavioral']).properties(height=300).interactive()
                st.altair_chart(chart, use_container_width=True)
            else: st.info("No mock data.")

# TAB 3: MASTER DATABASE
with tab3:
    cv, cdb = st.columns([1, 1])
    with cv:
        st.markdown("### 🏛️ MASTER VAULT")
        with st.expander("⬆️ UPLOAD NEW DOCUMENT"):
            up = st.file_uploader("Select File", type=["pdf", "docx", "txt", "csv"], key="dash_master_up")
            if up and st.button("💾 SAVE TO VAULT"):
                try:
                    cnt = ""
                    if up.name.lower().endswith('.pdf'): reader=PdfReader(up); cnt="\n".join([p.extract_text() for p in reader.pages])
                    elif up.name.lower().endswith('.docx'): doc=docx.Document(up); cnt="\n".join([p.text for p in doc.paragraphs])
                    elif up.name.lower().endswith('.txt'): cnt=str(up.read(), "utf-8")
                    conn=utils.get_db_connection(); cur=conn.cursor()
                    cur.execute("INSERT INTO global_kb (filename, content) VALUES (?, ?)", (up.name, cnt)); conn.commit()
                    cur.execute("SELECT * FROM global_kb"); st.session_state['global_kb']=[dict(row) for row in cur.fetchall()]
                    st.success(f"Uploaded: {up.name}"); st.rerun()
                except Exception as e: st.error(str(e))
        
        gkb = st.session_state.get('global_kb', [])
        if gkb:
            for d in gkb:
                with st.expander(f"📄 {d['filename']}"):
                    # Added unique keys to prevent duplicate ID error
                    st.text_area("Preview", value=d['content'][:1000]+"...", height=150, disabled=True, key=f"p_{d['id']}")
                    if st.button(f"🗑️ DELETE", key=f"pg_{d['id']}"):
                        conn=utils.get_db_connection(); cur=conn.cursor()
                        cur.execute("DELETE FROM global_kb WHERE id=?", (d['id'],)); conn.commit()
                        cur.execute("SELECT * FROM global_kb"); st.session_state['global_kb']=[dict(row) for row in cur.fetchall()]; st.rerun()
        else: st.warning("Vault Empty.")

    with cdb:
        st.markdown("### 🗄️ CLIENT LOGS")
        if client_db:
            df=pd.DataFrame(client_db)
            st.dataframe(df, use_container_width=True, height=500)
            st.download_button("💾 EXPORT CSV", df.to_csv(index=False).encode('utf-8'), "WSO_Backup.csv", "text/csv", type="primary", use_container_width=True)
        else: st.info("No clients.")