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
    div[data-testid="stVerticalBlock"] div[style*="border"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 40px -5px rgba(15, 23, 42, 0.12) !important;
    }
    button[kind="primary"] {
        background-color: #1e3a8a !important; 
        color: #ffffff !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(30, 58, 138, 0.2) !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        transition: all 0.2s;
    }
    button[kind="primary"]:hover { background-color: #172554 !important; box-shadow: 0 6px 15px rgba(30, 58, 138, 0.3) !important; }
    div[data-testid="stMetricValue"] { color: #1e3a8a !important; font-weight: 800 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. POŁĄCZENIE GOOGLE (SHEETS + DRIVE) ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Konfiguracja Google Drive API
def get_drive_service():
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build('drive', 'v3', credentials=creds)

DRIVE_SERVICE = get_drive_service()
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
        df = df.dropna(how='all') 
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_data(sheet_name, data):
    if not data:
        df = pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    else:
        df = pd.DataFrame(data)
    try:
        conn.update(worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")

def upload_pdf_to_drive(file_content, filename):
    if not FOLDER_ID: return ""
    file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf')
    file = DRIVE_SERVICE.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def download_pdf_from_drive(file_id):
    request = DRIVE_SERVICE.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return fh.getvalue()

def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in zam if str(x.get('id')) == str(order_id)), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order)
        zam = [x for x in zam if str(x.get('id')) != str(order_id)]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in hist if str(x.get('id')) == str(order_id)), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        hist = [x for x in hist if str(x.get('id')) != str(order_id)]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def move_dyspozycja_to_history(dysp_id):
    dyspo = load_data(DYSPOZYCJE_FILE)
    dyspo = [x for x in dyspo if str(x.get('id')) != str(dysp_id)]
    save_data(DYSPOZYCJE_FILE, dyspo)

# --- 4. SESJA I LOGOWANIE ---
if 'rola' not in st.session_state: st.session_state.rola = None

if st.session_state.rola is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #1e3a8a; font-weight: 800;'>WMS • Pakownia</h2>", unsafe_allow_html=True)
            st.write("")
            with st.form("login_form"):
                h = st.text_input("Hasło dostępu", type="password")
                if st.form_submit_button("ZALOGUJ DO SYSTEMU", use_container_width=True, type="primary"):
                    if h == HASLO_SZEFA: st.session_state.rola = 'szef'; st.rerun()
                    elif h == HASLO_PRACOWNIKA: st.session_state.rola = 'pracownik'; st.rerun()
                    else: st.toast("Nieprawidłowe hasło!", icon="❌")
else:
    # ==========================================
    #             PANEL ADMINISTRATORA
    # ==========================================
    if st.session_state.rola == 'szef':
        with st.sidebar:
            st.markdown("**Użytkownik:** Administrator 👨‍💼")
            if st.button("Wyloguj się", use_container_width=True):
                st.session_state.rola = None; st.rerun()

        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        dyspo_data = load_data(DYSPOZYCJE_FILE)
        zwroty_data = load_data(ZWROTY_FILE)
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="W kolejce", value=len(zam_data))
        m2.metric(label="Na dzisiaj", value=sum(1 for z in zam_data if str(z.get('termin', '9999-12-31')) <= dzisiaj_str))
        m3.metric(label="Spakowane dzisiaj", value=sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str)))
        m4.metric(label="Zwroty", value=sum(1 for z in zwroty_data if str(z.get('status')) == 'Nowy'))
        
        t1, t2, t3, t4, t5 = st.tabs(["➕ Nowe", "📦 Produkcja", "🗄️ Historia", "📝 Zadania", "↩️ Zwroty"])

        with t1:
            with st.form("add_form", clear_on_submit=True):
                nr = st.text_input("Numer zamówienia")
                termin = st.date_input("Termin", value=date.today())
                co = st.text_area("Specyfikacja")
                plik_etykiety = st.file_uploader("Etykieta (PDF)", type=["pdf"])
                if st.form_submit_button("DODAJ ZLECENIE", type="primary"):
                    if nr and co:
                        drive_id = ""
                        if plik_etykiety:
                            drive_id = upload_pdf_to_drive(plik_etykiety.read(), f"Etykieta_{nr}.pdf")
                        zam_data.append({"id": str(uuid.uuid4()), "nr": nr, "co": co, "termin": str(termin), "pdf_drive_id": drive_id})
                        zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                        save_data(ZAM_FILE, zam_data); st.toast("Dodano!"); st.rerun()

        with t2:
            for z in zam_data:
                with st.expander(f"ZAM: {z['nr']} | {z.get('termin')}"):
                    st.write(z['co'])
                    if st.button("Wycofaj", key=f"del_{z['id']}"):
                        zam_data = [x for x in zam_data if x['id'] != z['id']]; save_data(ZAM_FILE, zam_data); st.rerun()

        with t3:
            st.data_editor(hist_data, use_container_width=True)

        with t4:
            with st.form("dysp"):
                txt = st.text_area("Zadanie")
                if st.form_submit_button("Wyślij"):
                    dyspo_data.insert(0, {"id": str(uuid.uuid4()), "tresc": txt, "data_dodania": datetime.now().strftime("%H:%M")})
                    save_data(DYSPOZYCJE_FILE, dyspo_data); st.rerun()
            for d in dyspo_data: st.warning(f"{d['data_dodania']}: {d['tresc']}")

        with t5:
            for z in [x for x in zwroty_data if x.get('status') == 'Nowy']:
                st.error(f"Zwrot: {z['nr']} - {z['stan']}")
                if st.button("Zakończ RMA", key=f"rma_{z['id']}"):
                    for i in zwroty_data: 
                        if i['id'] == z['id']: i['status'] = 'Rozpatrzony'
                    save_data(ZWROTY_FILE, zwroty_data); st.rerun()

    # ==========================================
    #           TERMINAL PRACOWNIKA
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        zam_pracownik = load_data(ZAM_FILE)
        dyspo_pracownik = load_data(DYSPOZYCJE_FILE)
        
        # Audio Alert
        if 'znane_ids' not in st.session_state: st.session_state.znane_ids = {str(z['id']) for z in zam_pracownik}
        aktualne_ids = {str(z['id']) for z in zam_pracownik}
        if aktualne_ids - st.session_state.znane_ids:
            st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
        st.session_state.znane_ids = aktualne_ids

        c1, c2 = st.columns([8, 2])
        c1.title("TERMINAL PAKOWNI")
        if c2.button("🔄 ODŚWIEŻ", use_container_width=True): st.rerun()

        tab_kds, tab_dysp, tab_zwr = st.tabs(["📦 ZLECENIA", "📌 ZADANIA", "↩️ PRZYJMIJ ZWROT"])

        with tab_kds:
            cols = st.columns(3)
            for i, z in enumerate(zam_pracownik):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center;'><div style='font-size:40px; font-weight:900;'>{z['nr']}</div><hr><div>{z['co']}</div></div>", unsafe_allow_html=True)
                        
                        # Pobieranie PDF z Google Drive
                        d_id = z.get('pdf_drive_id', "")
                        if d_id:
                            try:
                                pdf_bytes = download_pdf_from_drive(d_id)
                                st.download_button("🖨️ ETYKIETA", data=pdf_bytes, file_name=f"{z['nr']}.pdf", mime="application/pdf", use_container_width=True)
                            except:
                                st.error("Błąd pobierania")
                        
                        if st.button("GOTOWE", key=f"go_{z['id']}", use_container_width=True, type="primary"):
                            move_to_history(z['id']); st.rerun()

        with tab_dysp:
            for d in dyspo_pracownik:
                st.info(d['tresc'])
                if st.button("Wykonano", key=f"d_{d['id']}"): move_dyspozycja_to_history(d['id']); st.rerun()

        with tab_zwr:
            with st.form("z"):
                nr = st.text_input("Nr zamówienia")
                stn = st.selectbox("Stan", ["Ok", "Uszkodzony"])
                if st.form_submit_button("Zgłoś"):
                    zwroty_data = load_data(ZWROTY_FILE)
                    zwroty_data.insert(0, {"id": str(uuid.uuid4()), "nr": nr, "stan": stn, "status": "Nowy", "data": datetime.now().strftime("%Y-%m-%d")})
                    save_data(ZWROTY_FILE, zwroty_data); st.success("Zgłoszono!")
