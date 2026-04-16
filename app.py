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

# --- 3. GOOGLE SHEETS BAZA DANYCH ---
conn = st.connection("gsheets", type=GSheetsConnection)

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"

LABELS_DIR = "etykiety" 
if not os.path.exists(LABELS_DIR):
    os.makedirs(LABELS_DIR)

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# Definicja nagłówków dla każdej karty (zapobiega błędowi przy pustych danych)
SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "ma_etykiete"],
    "Historia": ["id", "nr", "co", "termin", "ma_etykiete", "data_pakowania"],
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
    # Jeśli lista jest pusta, tworzymy DataFrame z samymi nagłówkami
    if not data:
        df = pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    else:
        df = pd.DataFrame(data)
    
    # Próba zapisu z obsługą błędów
    try:
        conn.update(worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"Błąd zapisu do Arkusza Google ({sheet_name}): {e}")

def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in zam if str(x.get('id')) == str(order_id)), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Dodajemy nagłówek jeśli go nie ma
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
if 'rola' not in st.session_state: 
    st.session_state.rola = None

if st.session_state.rola is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #1e3a8a; font-weight: 800;'>WMS • Pakownia</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #64748b;'>Zaloguj się do systemu magazynowego</p>", unsafe_allow_html=True)
            st.write("")
            with st.form("login_form"):
                h = st.text_input("Hasło dostępu", type="password")
                if st.form_submit_button("ZALOGUJ DO SYSTEMU", use_container_width=True, type="primary"):
                    if h == HASLO_SZEFA: 
                        st.session_state.rola = 'szef'
                        st.rerun()
                    elif h == HASLO_PRACOWNIKA: 
                        st.session_state.rola = 'pracownik'
                        st.rerun()
                    else: 
                        st.toast("Nieprawidłowe hasło!", icon="❌")

# --- 5. SYSTEM PO ZALOGOWANIU ---
else:

    # ==========================================
    #             PANEL ADMINISTRATORA
    # ==========================================
    if st.session_state.rola == 'szef':
        
        # --- ZMIANA: PRZYCISK WYLOGOWANIA NA GÓRZE, ZAMIAST W SIDEBARZE ---
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>PANEL SZEFA</h2>", unsafe_allow_html=True)
        c2.markdown("<div style='text-align: right; margin-top: 5px;'><b>Użytkownik:</b> Administrator 👨‍💼</div>", unsafe_allow_html=True)
        if c3.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()
        st.divider()
        # ------------------------------------------------------------------

        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        dyspo_data = load_data(DYSPOZYCJE_FILE)
        zwroty_data = load_data(ZWROTY_FILE)
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        
        do_spakowania_dzisiaj = sum(1 for z in zam_data if str(z.get('termin', '9999-12-31')) <= dzisiaj_str)
        spakowane_dzisiaj = sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str))
        oczekujace_zwroty = sum(1 for
