import streamlit as st
import json
import os
import uuid
import base64
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from datetime import datetime, date

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="System Zarządzania Wysyłką", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- 2. PROFESJONALNY CSS (Enterprise Design) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8fafc;
        color: #1e293b;
    }

    .stApp { background-color: #f8fafc; }
    .block-container { padding-top: 2rem; max-width: 95%; }

    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;} 
    [data-testid="collapsedControl"] {display: none !important;} 

    /* Nowoczesne Karty */
    div[data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 12px !important;
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
        padding: 24px !important;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stVerticalBlock"] div[style*="border"]:hover {
        box-shadow: 0 25px 30px -5px rgba(0, 0, 0, 0.08) !important;
        transform: translateY(-2px);
    }

    /* Przyciski Granatowe */
    button[kind="primary"] {
        background-color: #1e293b !important; 
        color: #ffffff !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.5rem !important;
        width: 100% !important;
        transition: 0.2s;
    }
    button[kind="primary"]:hover { background-color: #334155 !important; }

    /* Przycisk Drukowania - Naprawiony */
    .print-btn {
        display: block;
        width: 100%;
        text-align: center;
        padding: 10px 0;
        background-color: #ffffff;
        color: #1e293b;
        border: 2px solid #1e293b;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        margin-bottom: 12px;
        transition: all 0.2s;
    }
    .print-btn:hover { background-color: #1e293b; color: #ffffff; }

    div[data-testid="stMetricValue"] { color: #1e293b !important; font-weight: 700 !important; }
    h1, h2, h3 { color: #0f172a !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. POŁĄCZENIE I FUNKCJE DANYCH ---
conn = st.connection("gsheets", type=GSheetsConnection)

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"
ETYKIETY_FILE = "Etykiety"

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "ma_etykiete"],
    "Historia": ["id", "nr", "co", "termin", "ma_etykiete", "data_pakowania"],
    "Dyspozycje": ["id", "tresc", "data_dodania"],
    "Zwroty": ["id", "nr", "stan", "powod", "notatki", "status", "data", "data_rozpatrzenia"],
    "Etykiety": ["zam_id", "czesc", "dane"]
}

def load_data(sheet_name, force_refresh=False):
    try:
        ttl_value = 0 if force_refresh else "1m"
        df = conn.read(worksheet=sheet_name, ttl=ttl_value)
        df = df.dropna(how='all').fillna("") 
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_data(sheet_name, data):
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    try:
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear() 
    except Exception as e:
        st.error(f"Blad zapisu: {e}")

def usun_etykiete(order_id):
    etyk_data = load_data(ETYKIETY_FILE)
    nowe_etyk = [e for e in etyk_data if str(e.get('zam_id')) != str(order_id)]
    if len(nowe_etyk) != len(etyk_data): save_data(ETYKIETY_FILE, nowe_etyk)

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
        if str(order.get('ma_etykiete', '')).lower() in ['true', '1', 'prawda']: usun_etykiete(order_id)

def restore_from_history(order_id):
    zam, hist = load_data(ZAM_FILE), load_data(HIST_FILE)
    order = next((x for x in hist if str(x.get('id')) == str(order_id)), None)
    if order:
        order['ma_etykiete'] = "False"
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        hist = [x for x in hist if str(x.get('id')) != str(order_id)]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

# --- 4. LOGOWANIE ---
if 'rola' not in st.session_state: st.session_state.rola = None

if st.session_state.rola is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>LOGOWANIE</h2>", unsafe_allow_html=True)
            with st.form("login_form"):
                h = st.text_input("Haslo", type="password", placeholder="Wpisz haslo...")
                if st.form_submit_button("ZALOGUJ SIE", use_container_width=True, type="primary"):
                    if h == HASLO_SZEFA: st.session_state.rola = 'szef'; st.rerun()
                    elif h == HASLO_PRACOWNIKA: st.session_state.rola = 'pracownik'; st.rerun()
                    else: st.error("Nieprawidlowe haslo")

# --- 5. SYSTEM PO ZALOGOWANIU ---
else:
    if st.session_state.rola == 'szef':
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown("<h1 style='margin-top: -10px;'>PANEL ADMINISTRACYJNY</h1>", unsafe_allow_html=True)
        if c3.button("Wyloguj sie", use_container_width=True):
            st.session_state.rola = None; st.cache_data.clear(); st.rerun()
        st.divider()

        zam_data, hist_data, dyspo_data, zwroty_data = load_data(ZAM_FILE), load_data(HIST_FILE), load_data(DYSPOZYCJE_FILE), load_data(ZWROTY_FILE)
        etykiety_baza = load_data(ETYKIETY_FILE)
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("W kolejce", len(zam_data))
        m2.metric("Na dzis", sum(1 for z in zam_data if str(z.get('termin')) <= dzisiaj_str))
        m3.metric("Spakowane dzis", sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str)))
        m4.metric("Nowe zwroty", sum(1 for z in zwroty_data if str(z.get('status')) == 'Nowy'))
        
        st.write("<br>", unsafe_allow_html=True)
        t1, t2, t3, t4, t5 = st.tabs(["Nowe Zlecenie", "Aktywne", "Historia", "Zadania", "Zwroty"])

        with t1:
            with st.form("add_form", clear_on_submit=True):
                nr = st.text_input("Numer zamowienia")
                termin = st.date_input("Termin", value=date.today())
                co = st.text_area("Specyfikacja")
                plik = st.file_uploader("PDF", type=["pdf"])
                if st.form_submit_button("PRZEKAZ", type="primary") and nr and co:
                    new_id = str(uuid.uuid4())
                    if plik:
                        pdf_b64 = base64.b64encode(plik.read()).decode('utf-8')
                        chunk_size = 45000 
                        for idx, i in enumerate(range(0, len(pdf_b64), chunk_size)):
                            etykiety_baza.append({"zam_id": new_id, "czesc": idx, "dane": pdf_b64[i:i+chunk_size]})
                        save_data(ETYKIETY_FILE, etykiety_baza)
                    zam_data.append({"id": new_id, "nr": nr, "co": co, "termin": termin.strftime("%Y-%m-%d"), "ma_etykiete": "True" if plik else "False"})
                    save_data(ZAM_FILE, zam_data); st.rerun()

        with t2:
            for z in zam_data:
                with st.expander(f"Zam: {z['nr']} | {z['termin']}"):
                    if st.button("Usun", key=f"d_{z['id']}"):
                        save_data(ZAM_FILE, [x for x in zam_data if x['id'] != z['id']]); usun_etykiete(z['id']); st.rerun()

        with t3: st.data_editor(hist_data, use_container_width=True)

        with t5:
            for z in [x for x in zwroty_data if x['status'] == 'Nowy']:
                with st.container(border=True):
                    if st.button(f"Zalatwione: {z['nr']}", key=f"rz_{z['id']}", type="primary"):
                        for item in zwroty_data:
                            if item['id'] == z['id']: item['status'] = 'Rozpatrzony'
                        save_data(ZWROTY_FILE, zwroty_data); st.rerun()

    elif st.session_state.rola == 'pracownik':
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown("<h1 style='margin-top: -10px;'>KOMPLETACJA</h1>", unsafe_allow_html=True)
        if c2.button("Odswiez", use_container_width=True): st.cache_data.clear(); st.rerun()
        if c3.button("Wyloguj", use_container_width=True): st.session_state.rola = None; st.rerun()
        st.divider()

        zam_prac = load_data(ZAM_FILE)
        etyk_prac = load_data(ETYKIETY_FILE)

        if not zam_prac:
            st.write("<div style='text-align: center; padding: 100px; color: #94a3b8;'>Brak aktywnych zlecen</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(3)
            for i, z in enumerate(zam_prac):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"<p style='color: #64748b; font-size: 0.8rem; margin-bottom: 0;'>ZLECENIE</p>", unsafe_allow_html=True)
                        st.markdown(f"<h2 style='margin-top: 0; margin-bottom: 15px;'>{z['nr']}</h2>", unsafe_allow_html=True)
                        st.write(f"**Spec:** {z['co']}\n\n**Termin:** {z['termin']}")
                        st.write("<br>", unsafe_allow_html=True)
                        
                        # --- NAPRAWIONY PRZYCISK DRUKOWANIA (BLOB METHOD) ---
                        kawalki = [e for e in etyk_prac if str(e.get('zam_id')) == str(z['id'])]
                        if kawalki:
                            kawalki.sort(key=lambda x: int(x.get('czesc', 0)))
                            pdf_b64 = "".join([str(e.get('dane', '')) for e in kawalki])
                            
                            btn_id = f"btn_{z['id'].replace('-', '')}"
                            html_blob = f"""
                            <button id="{btn_id}" class="print-btn">DRUKUJ ETYKIETE</button>
                            <script>
                            document.getElementById("{btn_id}").onclick = function() {{
                                const b64 = "{pdf_b64}";
                                const byteCharacters = atob(b64);
                                const byteNumbers = new Array(byteCharacters.length);
                                for (let i = 0; i < byteCharacters.length; i++) {{
                                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                                }}
                                const byteArray = new Uint8Array(byteNumbers);
                                const blob = new Blob([byteArray], {{type: 'application/pdf'}});
                                const blobUrl = URL.createObjectURL(blob);
                                window.open(blobUrl, '_blank');
                            }};
                            </script>
                            """
                            components.html(html_blob, height=60)
                        
                        if st.button("ZAKONCZ", key=f"f_{z['id']}", type="primary"):
                            move_to_history(z['id']); st.rerun()
