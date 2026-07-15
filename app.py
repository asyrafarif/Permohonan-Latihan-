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
    conn.commit()
    conn.close()

def save_application(data):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""INSERT INTO applications
        (nama,jawatan,email,telefon,bahagian,unit,gred,pembiayaan,nama_latihan,tarikh_latihan,tempoh,tempat,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data['nama'], data['jawatan'], data['email'], data['telefon'], data['bahagian'], data['unit'], data['gred'],
        data['pembiayaan'], data['nama_latihan'], data['tarikh_latihan'], data['tempoh'], data['tempat'],
        'signed_by_applicant', datetime.utcnow().isoformat()
    ))
    app_id = c.lastrowid
    conn.commit()
    conn.close()
    return app_id

def save_signature(application_id, role, signer_name, img_bytes):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""INSERT INTO signatures (application_id, role, signer_name, signature, signed_at)
                 VALUES (?,?,?,?,?)""", (application_id, role, signer_name, img_bytes, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_pending_for_role(role):
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

def get_all_applications():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY created_at DESC", conn)
    conn.close()
    return df

def application_form():
    st.header("Borang Permohonan Latihan")
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
        st.write("Sila tandatangan di bawah:")
        canvas_result = st_canvas(
            stroke_width=2,
            stroke_color="#000",
            background_color="#fff",
            height=200,
            width=600,
            drawing_mode="freedraw",
            key="canvas",
        )
        submitted = st.form_submit_button("Hantar Permohonan dan Tandatangan")
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
            save_signature(app_id, 'Applicant', nama, img_bytes)
            # set application to pending for the right finance role
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            target_status = 'pending_BKT' if pembiayaan=='Akaun Amanah' else ('pending_BSM' if pembiayaan=='Akaun HCD' else 'pending_BKP')
            c.execute("UPDATE applications SET status=? WHERE id=?", (target_status, app_id))
            conn.commit()
            conn.close()
            st.success("Permohonan dihantar. ID: {}".format(app_id))

def approver_panel(role):
    st.header(f"Panel Kelulusan - {role}")

    # Use session state to remember which application the approver is viewing so UI persists across reruns
    if 'selected_app' not in st.session_state:
        st.session_state['selected_app'] = None

    pending = get_pending_for_role(role)
    if not pending:
        st.info("Tiada permohonan untuk diluluskan.")
        return

    for row in pending:
        app = dict(zip([ 'id','nama','jawatan','email','telefon','bahagian','unit','gred','pembiayaan','nama_latihan','tarikh_latihan','tempoh','tempat','status','created_at'], row))
        st.subheader(f"Permohonan ID: {app['id']} - {app['nama']}")
        st.write(app)

        # Button to open the signer view for this application. This sets session state so the canvas & inputs persist.
        if st.button(f"Lihat & Tandatangan - {app['id']}", key=f"view_{app['id']}"):
            st.session_state['selected_app'] = app['id']

        # If this application is selected, show the signature canvas and approve controls
        if st.session_state.get('selected_app') == app['id']:
            st.write("Klik tandatangan untuk setuju:")
            signer_name = st.text_input("Nama Pelulus", key=f"name_{app['id']}")
            canvas_result = st_canvas(
                stroke_width=2,
                stroke_color="#000",
                background_color="#fff",
                height=200,
                width=600,
                drawing_mode="freedraw",
                key=f"canvas_{app['id']}"
            )

            if st.button("Sahkan Kelulusan", key=f"approve_{app['id']}"):
                # Make sure the signer provided a name and signed
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
                    # update status
                    conn = sqlite3.connect(DB)
                    c = conn.cursor()
                    c.execute("UPDATE applications SET status=? WHERE id=?", ('approved_finance', app['id']))
                    conn.commit()
                    conn.close()
                    st.success("Permohonan diluluskan.")
                    # clear selection so approver can work on next application
                    st.session_state['selected_app'] = None


def hr_panel():
    st.header("Panel HR - Finalize & Cetak")
    df = get_all_applications()
    st.dataframe(df)
    app_id = st.number_input("Masukkan Application ID untuk lihat", min_value=1, step=1)
    if st.button("Lihat butiran"):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM applications WHERE id=?", (app_id,))
        row = c.fetchone()
        if not row:
            st.error("ID tidak ditemui.")
        else:
            st.write(dict(zip([ 'id','nama','jawatan','email','telefon','bahagian','unit','gred','pembiayaan','nama_latihan','tarikh_latihan','tempoh','tempat','status','created_at'], row)))
            # get signatures
            c.execute("SELECT role, signer_name, signed_at FROM signatures WHERE application_id=?", (app_id,))
            sigs = c.fetchall()
            st.write("Signatures:", sigs)
            if st.button("Finalize & Generate PDF"):
                # simple pdf generation
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, txt=f"Permohonan Latihan ID: {app_id}", ln=True)
                for k,v in zip([ 'nama','jawatan','email','telefon','bahagian','unit','gred','pembiayaan','nama_latihan','tarikh_latihan','tempoh','tempat'], row[1:13]):
                    pdf.cell(0,8, txt=f"{k}: {v}", ln=True)
                b = pdf.output(dest='S').encode('latin-1')
                b64 = base64.b64encode(b).decode()
                href = f"data:application/pdf;base64,{b64}"
                st.markdown(f"[Muat turun PDF]({href})")
                # update status
                c.execute("UPDATE applications SET status=? WHERE id=?", ('finalized_by_hr', app_id))
                conn.commit()
        conn.close()

def main():
    st.title("Sistem Permohonan Latihan (Demo)")
    init_db()
    # DEMO auth: pilih role (untuk dev). Gantikan dengan auth sebenar nanti.
    role = st.sidebar.selectbox("Log in sebagai (demo)", ['Pemohon','BKT','BSM','BKP','HR'])
    st.sidebar.write(f"Anda log in sebagai: {role}")
    if role == 'Pemohon':
        application_form()
    elif role in ['BKT','BSM','BKP']:
        approver_panel(role)
    elif role == 'HR':
        hr_panel()

if __name__ == '__main__':
    main()
