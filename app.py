import streamlit as st
import sqlite3
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io
from fpdf import FPDF
import base64
import pandas as pd

DB = "apps.db"

# Panel passwords - Pemohon tidak perlu password
PANEL_PASSWORDS = {
    'BKT': 'bkt123',
    'BSM': 'bsm123',
    'BKP': 'bkp123',
    'HR': 'hr123'
}

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT, jawatan TEXT, email TEXT, telefon TEXT, bahagian TEXT, unit TEXT, gred TEXT,
        pembiayaan TEXT, nama_latihan TEXT, tarikh_latihan TEXT, tempoh TEXT, tempat TEXT,
        status TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS signatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER,
        role TEXT,
        signer_name TEXT,
        signature BLOB,
        signed_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER,
        status TEXT,
        updated_at TEXT,
        updated_by TEXT
    )""")
    conn.commit()
    conn.close()

def log_status_change(application_id, new_status, updated_by='System'):
    """Record status changes in history for timeline"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""INSERT INTO status_history (application_id, status, updated_at, updated_by)
                 VALUES (?,?,?,?)""", (application_id, new_status, datetime.utcnow().isoformat(), updated_by))
    conn.commit()
    conn.close()

def get_status_timeline(application_id):
    """Get the timeline of status changes for an application"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status, updated_at, updated_by FROM status_history WHERE application_id=? ORDER BY updated_at ASC", (application_id,))
    timeline = c.fetchall()
    conn.close()
    return timeline

def save_application(data):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""INSERT INTO applications
        (nama,jawatan,email,telefon,bahagian,unit,gred,pembiayaan,nama_latihan,tarikh_latihan,tempoh,tempat,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data['nama'], data['jawatan'], data['email'], data['telefon'], data['bahagian'], data['unit'], data['gred'],
        data['pembiayaan'], data['nama_latihan'], data['tarikh_latihan'], data['tempoh'], data['tempat'],
        'submitted_by_applicant', datetime.utcnow().isoformat()
    ))
    app_id = c.lastrowid
    conn.commit()
    conn.close()
    # Log initial status
    log_status_change(app_id, 'submitted_by_applicant', data['nama'])
    return app_id

def save_signature(application_id, role, signer_name, img_bytes):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""INSERT INTO signatures (application_id, role, signer_name, signature, signed_at)
                 VALUES (?,?,?,?,?)""", (application_id, role, signer_name, img_bytes, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_pending_for_role(role):
    """Get applications pending approval by specific role"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Map role to pembiayaan pending status
    map_status = {
        'BKT': 'pending_BKT',
        'BSM': 'pending_BSM',
        'BKP': 'pending_BKP',
        'HR': 'approved_finance'  # HR sees approved_finance to finalize
    }
    status = map_status.get(role, '')
    if not status:
        return []
    c.execute("SELECT * FROM applications WHERE status=? ORDER BY created_at DESC", (status,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_application_by_id(app_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE id=?", (app_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(zip(['id','nama','jawatan','email','telefon','bahagian','unit','gred','pembiayaan','nama_latihan','tarikh_latihan','tempoh','tempat','status','created_at'], row))
    return None

def get_all_applications():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY created_at DESC", conn)
    conn.close()
    return df

def display_timeline(application_id):
    """Display application status timeline"""
    st.subheader("📊 Timeline Permohonan")
    timeline = get_status_timeline(application_id)
    
    if not timeline:
        st.info("Belum ada status yang direkod.")
        return
    
    # Status display with custom colors and descriptions
    status_descriptions = {
        'submitted_by_applicant': '🟦 Dihantar oleh Pemohon',
        'pending_BKT': '🟨 Menunggu Kelulusan BKT',
        'pending_BSM': '🟨 Menunggu Kelulusan BSM',
        'pending_BKP': '🟨 Menunggu Kelulusan BKP',
        'approved_bkt': '🟩 Diluluskan oleh BKT',
        'approved_bsm': '🟩 Diluluskan oleh BSM',
        'approved_bkp': '🟩 Diluluskan oleh BKP',
        'approved_finance': '🟩 Diluluskan oleh Kewangan',
        'finalized_by_hr': '🟪 Difinaliskan oleh HR'
    }
    
    for status, updated_at, updated_by in timeline:
        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            st.write(status_descriptions.get(status, f"ℹ️ {status}"))
        with col2:
            st.write(f"**{updated_by}**")
        with col3:
            st.write(f"_{datetime.fromisoformat(updated_at).strftime('%d/%m/%Y %H:%M')}_")

def login_panel(panel_name):
    """Handle password authentication for each panel (not needed for Pemohon)"""
    if panel_name == 'Pemohon':
        return True
    
    if f'{panel_name}_authenticated' not in st.session_state:
        st.session_state[f'{panel_name}_authenticated'] = False
    
    if not st.session_state[f'{panel_name}_authenticated']:
        st.warning(f"🔒 Sila masukkan kata laluan untuk akses Panel {panel_name}")
        password = st.text_input(f"Kata Laluan Panel {panel_name}", type="password")
        if st.button(f"Log masuk ke Panel {panel_name}"):
            if password == PANEL_PASSWORDS.get(panel_name, ''):
                st.session_state[f'{panel_name}_authenticated'] = True
                st.success(f"Anda sudah log masuk ke Panel {panel_name}!")
                st.rerun()
            else:
                st.error("Kata laluan salah. Sila cuba lagi.")
        return False
    return True

def application_form():
    """Applicant panel - no password needed"""
    st.header("📝 Borang Permohonan Latihan")
    with st.form("permohonan"):
        nama = st.text_input("Nama")
        jawatan = st.text_input("Jawatan")
        email = st.text_input("Email")
        telefon = st.text_input("No Telefon")
        bahagian = st.text_input("Bahagian")
        unit = st.text_input("Unit")
        gred = st.text_input("Gred")
        pembiayaan = st.selectbox("Pembiayaan", ['Akaun Amanah','Akaun HCD','Akaun Mengurus'])
        nama_latihan = st.text_input("Nama Latihan")
        tarikh_latihan = st.date_input("Tarikh Latihan")
        tempoh = st.text_input("Tempoh Latihan (hari/jam)")
        tempat = st.text_input("Tempat Latihan")
        st.write("✍️ Sila tandatangan di bawah:")
        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color="#000",
            background_color="#fff",
            height=200,
            width=600,
            drawing_mode="freedraw",
            key="canvas",
        )
        submitted = st.form_submit_button("📤 Hantar Permohonan dan Tandatangan")
        if submitted:
            if canvas_result.image_data is None:
                st.error("Sila tandatangan sebelum hantar.")
                return
            data = {
                'nama': nama,
                'jawatan': jawatan,
                'email': email,
                'telefon': telefon,
                'bahagian': bahagian,
                'unit': unit,
                'gred': gred,
                'pembiayaan': pembiayaan,
                'nama_latihan': nama_latihan,
                'tarikh_latihan': tarikh_latihan.isoformat(),
                'tempoh': tempoh,
                'tempat': tempat
            }
            app_id = save_application(data)
            # save signature image as PNG bytes
            img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            img_bytes = buf.getvalue()
            save_signature(app_id, 'Pemohon', nama, img_bytes)
            # set application to pending for the right finance role based on pembiayaan
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            if pembiayaan == 'Akaun Amanah':
                target_status = 'pending_BKT'
            elif pembiayaan == 'Akaun HCD':
                target_status = 'pending_BSM'
            else:  # Akaun Mengurus
                target_status = 'pending_BKP'
            c.execute("UPDATE applications SET status=? WHERE id=?", (target_status, app_id))
            conn.commit()
            conn.close()
            log_status_change(app_id, target_status, nama)
            st.success(f"✅ Permohonan dihantar. ID Permohonan: **{app_id}**")
            st.info("Sila simpan ID permohonan anda untuk rujukan di masa depan.")
    
    # Applicant can check their application status
    st.divider()
    st.subheader("📋 Semak Status Permohonan")
    app_id = st.number_input("Masukkan ID Permohonan anda:", min_value=1, step=1)
    if st.button("Cari"):
        app = get_application_by_id(app_id)
        if app:
            st.write(f"**Nama:** {app['nama']}")
            st.write(f"**Status:** {app['status']}")
            display_timeline(app_id)
            
            # PDF download option
            if st.button(f"📥 Muat turun Permohonan sebagai PDF"):
                generate_and_download_pdf(app, app_id)
        else:
            st.error(f"ID permohonan {app_id} tidak ditemui.")

def generate_and_download_pdf(app, app_id):
    """Generate PDF for application"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="PERMOHONAN LATIHAN", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    
    pdf.cell(0, 8, txt=f"ID Permohonan: {app_id}", ln=True)
    pdf.cell(0, 8, txt=f"Tarikh Hantar: {datetime.fromisoformat(app['created_at']).strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="MAKLUMAT PERIBADI", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Nama: {app['nama']}", ln=True)
    pdf.cell(0, 6, txt=f"Jawatan: {app['jawatan']}", ln=True)
    pdf.cell(0, 6, txt=f"Email: {app['email']}", ln=True)
    pdf.cell(0, 6, txt=f"Telefon: {app['telefon']}", ln=True)
    pdf.cell(0, 6, txt=f"Bahagian: {app['bahagian']}", ln=True)
    pdf.cell(0, 6, txt=f"Unit: {app['unit']}", ln=True)
    pdf.cell(0, 6, txt=f"Gred: {app['gred']}", ln=True)
    pdf.ln(3)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="MAKLUMAT LATIHAN", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Nama Latihan: {app['nama_latihan']}", ln=True)
    pdf.cell(0, 6, txt=f"Tarikh Latihan: {app['tarikh_latihan']}", ln=True)
    pdf.cell(0, 6, txt=f"Tempoh: {app['tempoh']}", ln=True)
    pdf.cell(0, 6, txt=f"Tempat: {app['tempat']}", ln=True)
    pdf.cell(0, 6, txt=f"Pembiayaan: {app['pembiayaan']}", ln=True)
    pdf.cell(0, 6, txt=f"Status: {app['status']}", ln=True)
    
    b = pdf.output(dest='S').encode('latin-1')
    b64 = base64.b64encode(b).decode()
    href = f"data:application/pdf;base64,{b64}"
    st.markdown(f"[⬇️ Muat Turun PDF]({href})", unsafe_allow_html=True)

def approver_panel(role):
    """Approver panel for BKT, BSM, BKP"""
    if not login_panel(role):
        return
    
    st.header(f"✅ Panel Kelulusan - {role}")
    
    # Use session state to remember which application the approver is viewing
    if f'selected_app_{role}' not in st.session_state:
        st.session_state[f'selected_app_{role}'] = None
    
    pending = get_pending_for_role(role)
    if not pending:
        st.info(f"Tiada permohonan untuk diluluskan oleh {role}.")
        return
    
    st.subheader(f"Permohonan Menunggu Kelulusan {role} ({len(pending)} item)")
    
    for row in pending:
        app = dict(zip(['id','nama','jawatan','email','telefon','bahagian','unit','gred','pembiayaan','nama_latihan','tarikh_latihan','tempoh','tempat','status','created_at'], row))
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**ID {app['id']}** - {app['nama']} ({app['jawatan']})")
        with col2:
            if st.button("Lihat & Tandatangan", key=f"view_{app['id']}"):
                st.session_state[f'selected_app_{role}'] = app['id']
        
        # If this application is selected, show the signature canvas and approve controls
        if st.session_state.get(f'selected_app_{role}') == app['id']:
            with st.expander(f"📝 Borang Permohonan #{app['id']}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Email:** {app['email']}")
                    st.write(f"**Telefon:** {app['telefon']}")
                with col2:
                    st.write(f"**Bahagian:** {app['bahagian']}")
                    st.write(f"**Unit:** {app['unit']}")
                with col3:
                    st.write(f"**Gred:** {app['gred']}")
                    st.write(f"**Pembiayaan:** {app['pembiayaan']}")
                
                st.write(f"**Latihan:** {app['nama_latihan']} ({app['tempoh']}) - {app['tempat']}")
                st.write(f"**Tarikh:** {app['tarikh_latihan']}")
                
                display_timeline(app['id'])
                
                st.divider()
                st.write("✍️ Tandatangan untuk Kelulusan:")
                signer_name = st.text_input("Nama Pelulus", key=f"name_{app['id']}")
                canvas_result = st_canvas(
                    stroke_width=2,
                    stroke_color="#000",
                    background_color="#fff",
                    height=150,
                    width=400,
                    drawing_mode="freedraw",
                    key=f"canvas_{app['id']}"
                )
                
                if st.button("✅ Sahkan Kelulusan", key=f"approve_{app['id']}"):
                    if not signer_name:
                        st.error("Sila masukkan nama pelulus.")
                    elif canvas_result is None or canvas_result.image_data is None:
                        st.error("Sila tandatangan sebelum sahkan.")
                    else:
                        img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        img_bytes = buf.getvalue()
                        save_signature(app['id'], role, signer_name, img_bytes)
                        
                        # Update status based on which role approved it
                        conn = sqlite3.connect(DB)
                        c = conn.cursor()
                        
                        # Map role to approved status
                        if role == 'BKT':
                            new_status = 'approved_bkt'
                        elif role == 'BSM':
                            new_status = 'approved_bsm'
                        elif role == 'BKP':
                            new_status = 'approved_bkp'
                        else:
                            new_status = 'approved_finance'
                        
                        c.execute("UPDATE applications SET status=? WHERE id=?", (new_status, app['id']))
                        conn.commit()
                        conn.close()
                        log_status_change(app['id'], new_status, signer_name)
                        
                        st.success(f"✅ Permohonan diluluskan oleh {role}!")
                        # clear selection
                        st.session_state[f'selected_app_{role}'] = None
                        st.rerun()

def hr_panel():
    """HR panel for finalizing and generating PDFs"""
    if not login_panel('HR'):
        return
    
    st.header("👔 Panel HR - Finalize & Cetak")
    
    df = get_all_applications()
    st.write(f"Jumlah permohonan: **{len(df)}**")
    
    # Filter by status
    status_options = ['Semua', 'submitted_by_applicant', 'pending_BKT', 'pending_BSM', 'pending_BKP', 
                      'approved_bkt', 'approved_bsm', 'approved_bkp', 'approved_finance', 'finalized_by_hr']
    status_filter = st.selectbox("Filter mengikut status", status_options)
    
    if status_filter != 'Semua':
        df = df[df['status'] == status_filter]
    
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    st.subheader("Finalisasi Permohonan")
    app_id = st.number_input("Masukkan Application ID untuk lihat", min_value=1, step=1)
    
    if st.button("Lihat butiran"):
        app = get_application_by_id(app_id)
        if app:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Nama:** {app['nama']}")
                st.write(f"**Email:** {app['email']}")
            with col2:
                st.write(f"**Jawatan:** {app['jawatan']}")
                st.write(f"**Bahagian:** {app['bahagian']}")
            with col3:
                st.write(f"**Gred:** {app['gred']}")
                st.write(f"**Status:** {app['status']}")
            
            st.divider()
            st.write("**Maklumat Latihan:**")
            st.write(f"- Nama: {app['nama_latihan']}")
            st.write(f"- Tarikh: {app['tarikh_latihan']}")
            st.write(f"- Tempoh: {app['tempoh']}")
            st.write(f"- Tempat: {app['tempat']}")
            st.write(f"- Pembiayaan: {app['pembiayaan']}")
            
            st.divider()
            display_timeline(app_id)
            
            st.divider()
            # get signatures
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("SELECT role, signer_name, signed_at FROM signatures WHERE application_id=?", (app_id,))
            sigs = c.fetchall()
            if sigs:
                st.write("**Tandatangan:**")
                for role, signer_name, signed_at in sigs:
                    st.write(f"- {role}: {signer_name} ({datetime.fromisoformat(signed_at).strftime('%d/%m/%Y %H:%M')})")
            conn.close()
            
            if st.button("📥 Finalize & Generate PDF"):
                generate_and_download_pdf(app, app_id)
                # update status
                conn = sqlite3.connect(DB)
                c = conn.cursor()
                c.execute("UPDATE applications SET status=? WHERE id=?", ('finalized_by_hr', app_id))
                conn.commit()
                conn.close()
                log_status_change(app_id, 'finalized_by_hr', 'HR')
                st.success("✅ Permohonan telah difinaliskan!")
        else:
            st.error(f"ID permohonan {app_id} tidak ditemui.")

def main():
    st.set_page_config(page_title="Sistem Permohonan Latihan", page_icon="📋", layout="wide")
    st.title("📋 Sistem Permohonan Latihan")
    init_db()
    
    # Logout button in sidebar
    if st.sidebar.button("🚪 Log Keluar"):
        for key in list(st.session_state.keys()):
            if 'authenticated' in key:
                st.session_state[key] = False
        st.rerun()
    
    # Panel selection
    panel = st.sidebar.radio("Pilih Panel", ['Pemohon', 'BKT', 'BSM', 'BKP', 'HR'])
    
    if panel == 'Pemohon':
        application_form()
    elif panel in ['BKT', 'BSM', 'BKP']:
        approver_panel(panel)
    elif panel == 'HR':
        hr_panel()

if __name__ == '__main__':
    main()
