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
    button[kind="primary"] {
        background-color: #1e3a8a !important; 
        color: #ffffff !important;
        border-radius: 8px !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. GOOGLE SHEETS BAZA DANYCH ---
conn = st.connection("gsheets", type=GSheetsConnection)

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"
ETYKIETY_FILE = "Etykiety"

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# Definicja nagłówków - BARDZO WAŻNE dla stabilności Google Sheets
SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "ma_etykiete"],
    "Historia": ["id", "nr", "co", "termin", "ma_etykiete", "data_pakowania"],
    "Dyspozycje": ["id", "tresc", "data_dodania"],
    "Zwroty": ["id", "nr", "stan", "powod", "notatki", "status", "data", "data_rozpatrzenia"],
    "Etykiety": ["zam_id", "czesc", "dane"]
}

def load_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        df = df.dropna(how='all') 
        df = df.fillna("") 
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_data(sheet_name, data):
    headers = SHEET_HEADERS.get(sheet_name, [])
    if not data:
        df = pd.DataFrame(columns=headers)
    else:
        df = pd.DataFrame(data)
        # POPRAWKA: Upewnij się, że DF ma tylko wymagane kolumny w odpowiedniej kolejności
        for col in headers:
            if col not in df.columns:
                df[col] = ""
        df = df[headers]
    
    try:
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear() # Czyścimy cache, by wymusić odświeżenie danych
    except Exception as e:
        st.error(f"Błąd zapisu do Arkusza Google ({sheet_name}): {e}")

def usun_etykiete(order_id):
    etyk_data = load_data(ETYKIETY_FILE)
    nowe_etyk = [e for e in etyk_data if str(e.get('zam_id')) != str(order_id)]
    if len(nowe_etyk) != len(etyk_data):
        save_data(ETYKIETY_FILE, nowe_etyk)

def move_to_history(order_id):
    # 1. Pobierz aktualne dane
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    
    # 2. Znajdź zamówienie
    order_idx = next((i for i, x in enumerate(zam) if str(x.get('id')) == str(order_id)), None)
    
    if order_idx is not None:
        # 3. Stwórz kopię zamówienia do historii i dodaj datę
        order_to_hist = zam[order_idx].copy()
        order_to_hist['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 4. Dodaj do historii na początek
        hist.insert(0, order_to_hist)
        
        # 5. Usuń z aktywnych
        nowe_zam = [x for i, x in enumerate(zam) if i != order_idx]
        
        # 6. ZAPISZ W KOLEJNOŚCI (najpierw historia, potem usunięcie z aktywnych)
        save_data(HIST_FILE, hist)
        save_data(ZAM_FILE, nowe_zam)
        
        # 7. Usuń powiązaną etykietę
        usun_etykiete(order_id)
        return True
    return False

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order_idx = next((i for i, x in enumerate(hist) if str(x.get('id')) == str(order_id)), None)
    
    if order_idx is not None:
        order = hist[order_idx].copy()
        if 'data_pakowania' in order: del order['data_pakowania']
        order['ma_etykiete'] = "False" 
        
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        
        nowa_hist = [x for i, x in enumerate(hist) if i != order_idx]
        
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, nowa_hist)

def move_dyspozycja_to_history(dysp_id):
    dyspo = load_data(DYSPOZYCJE_FILE)
    dyspo = [x for x in dyspo if str(x.get('id')) != str(dysp_id)]
    save_data(DYSPOZYCJE_FILE, dyspo)

# --- 4. SESJA I LOGOWANIE (Bez zmian) ---
if 'rola' not in st.session_state: 
    st.session_state.rola = None

if st.session_state.rola is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #1e3a8a; font-weight: 800;'>WMS • Pakownia</h2>", unsafe_allow_html=True)
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
    if st.session_state.rola == 'szef':
        # ... (Reszta kodu Panelu Szefa bez zmian, poza ewentualnym upewnieniem się że pobiera świeże dane) ...
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>PANEL SZEFA</h2>", unsafe_allow_html=True)
        if c3.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()
        st.divider()

        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        dyspo_data = load_data(DYSPOZYCJE_FILE)
        zwroty_data = load_data(ZWROTY_FILE)
        etykiety_baza = load_data(ETYKIETY_FILE)
        
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="Wszystkie w kolejce", value=len(zam_data))
        m2.metric(label="Wymagane na dzisiaj", value=sum(1 for z in zam_data if str(z.get('termin', '')) <= dzisiaj_str))
        m3.metric(label="Spakowane dzisiaj", value=sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str)))
        st.divider()
        
        t1, t2, t3, t4, t5 = st.tabs(["➕ Nowe Zlecenie", "📦 Aktywne na Produkcji", "🗄️ Baza Historyczna", "📝 Zadania", "↩️ Zwroty i Reklamacje"])

        with t1:
            with st.form("add_form", clear_on_submit=True):
                st.markdown("#### Utwórz nowe zlecenie kompletacji")
                nr = st.text_input("Indeks / Numer zamówienia")
                termin = st.date_input("Wymagany termin realizacji", value=date.today())
                co = st.text_area("Specyfikacja (co spakować)")
                plik_etykiety = st.file_uploader("Załącz list przewozowy / etykietę (PDF)", type=["pdf"])
                
                if st.form_submit_button("PRZEKAŻ NA MAGAZYN", type="primary"):
                    if nr and co:
                        new_id = str(uuid.uuid4())
                        if plik_etykiety is not None:
                            pdf_b64 = base64.b64encode(plik_etykiety.read()).decode('utf-8')
                            chunk_size = 45000 
                            for idx, i in enumerate(range(0, len(pdf_b64), chunk_size)):
                                chunk = pdf_b64[i:i+chunk_size]
                                etykiety_baza.append({"zam_id": new_id, "czesc": idx, "dane": chunk})
                            save_data(ETYKIETY_FILE, etykiety_baza)

                        zam_data.append({
                            "id": new_id, "nr": nr, "co": co, 
                            "termin": termin.strftime("%Y-%m-%d"),
                            "ma_etykiete": "True"
                        })
                        zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                        save_data(ZAM_FILE, zam_data)
                        st.toast(f"Dodano: {nr}", icon="✅")
                        st.rerun() 

        with t2:
            for z in zam_data:
                with st.expander(f"ZAM: {z['nr']} | Termin: {z.get('termin')}"):
                    if st.button("Usuń", key=f"boss_del_{z['id']}"):
                        zam_data = [x for x in zam_data if str(x.get('id')) != str(z['id'])]
                        save_data(ZAM_FILE, zam_data)
                        usun_etykiete(z['id'])
                        st.rerun()

        with t3:
            for h in hist_data:
                with st.expander(f"✔️ ZAM: {h.get('nr')} | Wykonano: {h.get('data_pakowania')}"):
                    if st.button("Przywróć na produkcję", key=f"boss_rev_{h['id']}"):
                        restore_from_history(h['id'])
                        st.rerun()

        # ... Pozostałe taby (t4, t5) analogicznie ...

    elif st.session_state.rola == 'pracownik':
        zam_pracownik = load_data(ZAM_FILE)
        dyspo_pracownik = load_data(DYSPOZYCJE_FILE)
        
        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież"): st.rerun()
        if c3.button("Wyloguj"): 
            st.session_state.rola = None
            st.rerun()

        tab_kds, tab_dyspo, tab_zwroty, tab_hist = st.tabs(["📦 AKTYWNE ZLECENIA", "📌 ZADANIA", "↩️ ZWROT", "🕒 OSTATNIE"])

        with tab_kds:
            if not zam_pracownik:
                st.info("Brak zleceń")
            else:
                cols = st.columns(3)
                etykiety_pracownik = load_data(ETYKIETY_FILE)
                for i, z in enumerate(zam_pracownik):
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"### {z.get('nr')}\n\n{z.get('co')}")
                            
                            # Logika etykiety
                            kawalki = [e for e in etykiety_pracownik if str(e.get('zam_id')) == str(z['id'])]
                            if kawalki:
                                kawalki.sort(key=lambda x: int(x.get('czesc', 0)))
                                pdf_b64 = "".join([str(e.get('dane', '')) for e in kawalki])
                                # (Tutaj kod JS do drukowania - pozostaje bez zmian jak w Twoim kodzie)
                                if st.button("🖨️ DRUKUJ", key=f"p_{z['id']}"):
                                    st.info("Etykieta gotowa do druku")

                            if st.button("✅ ZAKOŃCZ ZLECENIE", key=f"fin_{z['id']}", use_container_width=True, type="primary"):
                                if move_to_history(z['id']):
                                    st.toast("Zlecenie zakończone!")
                                    st.rerun()

        with tab_hist:
            hist_p = load_data(HIST_FILE)[:10]
            for h in hist_p:
                st.write(f"✔️ {h.get('nr')} - {h.get('data_pakowania')}")
