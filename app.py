import streamlit as st
import json
import os
import uuid
import base64
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io
from datetime import datetime, date

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pakownia | System Zarządzania", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- 2. PROFESJONALNY CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f4f6f9; }
    .block-container { padding-top: 2rem; max-width: 98%; padding-bottom: 2rem; }
    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;} 
    [data-testid="collapsedControl"] {display: none !important;} 
    div[data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 16px !important;
        background-color: #ffffff !important;
        border: none !important;
        box-shadow: 0 10px 30px -5px rgba(15, 23, 42, 0.08) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    button[kind="primary"] {
        background-color: #1e3a8a !important; 
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] { color: #1e3a8a !important; font-weight: 800 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. POŁĄCZENIE GOOGLE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_drive_service():
    info = st.secrets["connections"]["gsheets"]
    # Kluczowe: musimy mieć scope do Drive
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build('drive', 'v3', credentials=creds)

try:
    DRIVE_SERVICE = get_drive_service()
except Exception as e:
    st.error(f"Problem z logowaniem do Google Drive: {e}")

FOLDER_ID = st.secrets.get("drive_folder_id", "")

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "pdf_drive_id"],
    "Historia": ["id", "nr", "co", "termin", "pdf_drive_id", "data_pakowania"],
    "Dyspozycje": ["id", "tresc", "data_dodania"],
    "Zwroty": ["id", "nr", "stan", "powod", "notatki", "status", "data", "data_rozpatrzenia"]
}

def load_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df.dropna(how='all').to_dict(orient="records")
    except: return []

def save_data(sheet_name, data):
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    conn.update(worksheet=sheet_name, data=df)

def upload_pdf_to_drive(file_content, filename):
    try:
        file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf')
        file = DRIVE_SERVICE.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Błąd wysyłania na Drive: {e}")
        return ""

def download_pdf_from_drive(file_id):
    try:
        request = DRIVE_SERVICE.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        return f"ERROR: {str(e)}"

def move_to_history(order_id):
    zam, hist = load_data(ZAM_FILE), load_data(HIST_FILE)
    order = next((x for x in zam if str(x.get('id')) == str(order_id)), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order)
        save_data(HIST_FILE, hist)
        save_data(ZAM_FILE, [x for x in zam if str(x.get('id')) != str(order_id)])

def restore_from_history(order_id):
    zam, hist = load_data(ZAM_FILE), load_data(HIST_FILE)
    order = next((x for x in hist if str(x.get('id')) == str(order_id)), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, [x for x in hist if str(x.get('id')) != str(order_id)])

# --- 4. LOGOWANIE ---
if 'rola' not in st.session_state: st.session_state.rola = None

if st.session_state.rola is None:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br><h2 style='text-align: center; color: #1e3a8a;'>WMS • Pakownia</h2>", unsafe_allow_html=True)
        with st.form("login"):
            h = st.text_input("Hasło", type="password")
            if st.form_submit_button("ZALOGUJ", use_container_width=True):
                if h == HASLO_SZEFA: st.session_state.rola = 'szef'; st.rerun()
                elif h == HASLO_PRACOWNIKA: st.session_state.rola = 'pracownik'; st.rerun()
                else: st.toast("Błędne hasło!")
else:
    if st.session_state.rola == 'szef':
        # --- PANEL SZEFA ---
        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        dyspo_data = load_data(DYSPOZYCJE_FILE)
        zwroty_data = load_data(ZWROTY_FILE)
        dzisiaj = datetime.now().strftime("%Y-%m-%d")

        st.markdown(f"### 📊 Przegląd Operacyjny")
        m1, m2, m3 = st.columns(3)
        m1.metric("W kolejce", len(zam_data))
        m2.metric("Spakowane dziś", sum(1 for h in hist_data if str(h.get('data_pakowania','')).startswith(dzisiaj)))
        m3.metric("Aktywne zadania", len(dyspo_data))

        t1, t2, t3, t4, t5 = st.tabs(["➕ Dodaj", "📦 Produkcja", "🗄️ Historia", "📝 Zadania", "↩️ Zwroty"])

        with t1:
            with st.form("add"):
                nr = st.text_input("Nr zamówienia")
                trm = st.date_input("Termin", value=date.today())
                spec = st.text_area("Co spakować")
                file = st.file_uploader("Etykieta PDF", type=['pdf'])
                if st.form_submit_button("WYŚLIJ NA PRODUKCJĘ", type="primary"):
                    if nr and spec:
                        d_id = upload_pdf_to_drive(file.read(), f"Etykieta_{nr}.pdf") if file else ""
                        zam_data.append({"id": str(uuid.uuid4()), "nr": nr, "co": spec, "termin": str(trm), "pdf_drive_id": d_id})
                        zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                        save_data(ZAM_FILE, zam_data); st.rerun()

        with t2:
            for z in zam_data:
                with st.expander(f"ZAM: {z['nr']} | {z.get('termin')}"):
                    st.write(z['co'])
                    if st.button("Usuń", key=f"del_{z['id']}"):
                        save_data(ZAM_FILE, [x for x in zam_data if x['id'] != z['id']]); st.rerun()

        with t3:
            st.data_editor(hist_data, use_container_width=True)

        with t4:
            with st.form("d_add"):
                txt = st.text_area("Nowe zadanie")
                if st.form_submit_button("Dodaj"):
                    dyspo_data.insert(0, {"id": str(uuid.uuid4()), "tresc": txt, "data_dodania": datetime.now().strftime("%H:%M")})
                    save_data(DYSPOZYCJE_FILE, dyspo_data); st.rerun()
            for d in dyspo_data: st.info(f"{d['data_dodania']}: {d['tresc']}")

        with t5:
            for r in [x for x in zwroty_data if x.get('status') == 'Nowy']:
                st.error(f"Zwrot: {r['nr']}")
                if st.button("Zamknij", key=f"r_{r['id']}"):
                    for i in zwroty_data: 
                        if i['id'] == r['id']: i['status'] = 'Rozpatrzony'
                    save_data(ZWROTY_FILE, zwroty_data); st.rerun()

    elif st.session_state.rola == 'pracownik':
        # --- PANEL PRACOWNIKA ---
        zam_p = load_data(ZAM_FILE)
        dys_p = load_data(DYSPOZYCJE_FILE)
        
        # Audio Alert
        if 'old_ids' not in st.session_state: st.session_state.old_ids = {str(z['id']) for z in zam_p}
        curr_ids = {str(z['id']) for z in zam_p}
        if curr_ids - st.session_state.old_ids:
            st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
        st.session_state.old_ids = curr_ids

        c1, c2 = st.columns([8, 2])
        c1.title("TERMINAL PAKOWNI")
        if c2.button("🔄 ODŚWIEŻ"): st.rerun()

        tab_z, tab_d, tab_r = st.tabs(["📦 ZLECENIA", "📌 ZADANIA", "↩️ ZWROT"])

        with tab_z:
            cols = st.columns(3)
            for i, z in enumerate(zam_p):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center;'><div style='font-size:45px; font-weight:900;'>{z['nr']}</div><hr><div>{z['co']}</div></div>", unsafe_allow_html=True)
                        
                        # LOGIKA POBIERANIA PDF
                        d_id = z.get('pdf_drive_id', "")
                        if d_id and len(str(d_id)) > 5:
                            res = download_pdf_from_drive(d_id)
                            if isinstance(res, bytes):
                                st.download_button("🖨️ DRUKUJ ETYKIETĘ", data=res, file_name=f"{z['nr']}.pdf", mime="application/pdf", use_container_width=True)
                            else:
                                st.error(f"Błąd PDF: {res}") # Tu wyświetli konkretny powód błędu
                        
                        if st.button("GOTOWE", key=f"fin_{z['id']}", use_container_width=True, type="primary"):
                            move_to_history(z['id']); st.rerun()

        with tab_d:
            for d in dys_p:
                st.warning(d['tresc'])
                if st.button("Wykonane", key=f"dp_{d['id']}"):
                    save_data(DYSPOZYCJE_FILE, [x for x in dys_p if x['id'] != d['id']]); st.rerun()

        with tab_r:
            with st.form("r_form"):
                nr_r = st.text_input("Nr zamówienia")
                if st.form_submit_button("Zgłoś zwrot"):
                    rd = load_data(ZWROTY_FILE)
                    rd.insert(0, {"id": str(uuid.uuid4()), "nr": nr_r, "status": "Nowy", "data": datetime.now().strftime("%Y-%m-%d")})
                    save_data(ZWROTY_FILE, rd); st.success("Zgłoszono!")
