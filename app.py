import streamlit as st
import json
import os
import uuid
from datetime import datetime

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pakownia | System Zarządzania", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- 2. PROFESJONALNY CSS (Globalny) ---
st.markdown("""
<style>
    /* Globalne marginesy */
    .block-container {padding-top: 2rem; max-width: 98%; padding-bottom: 2rem;}
    
    /* Profesjonalne kafelki (Karty) z efektem cienia */
    div[data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        border: 1px solid #f0f0f0 !important;
        background-color: #ffffff;
        transition: transform 0.1s ease-in-out, box-shadow 0.1s ease-in-out;
    }
    
    /* Efekt najechania myszką (Hover) */
    div[data-testid="stVerticalBlock"] div[style*="border"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1) !important;
    }
    
    /* Stylizacja metryk w Dashboardzie */
    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. BAZA DANYCH ---
ZAM_FILE = "zamowienia.json"
HIST_FILE = "historia.json"
HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

def load_data(file):
    if not os.path.exists(file): return []
    with open(file, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in zam if x['id'] == order_id), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order)
        zam = [x for x in zam if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in hist if x['id'] == order_id), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order)
        hist = [x for x in hist if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

# --- 4. SESJA I LOGOWANIE ---
if 'rola' not in st.session_state: 
    st.session_state.rola = None

if st.session_state.rola is None:
    # Wyśrodkowany ekran logowania
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #333;'>WMS • Pakownia</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #666;'>Zaloguj się, aby uzyskać dostęp</p>", unsafe_allow_html=True)
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
        
        # Pasek boczny TYLKO dla Szefa
        with st.sidebar:
            st.markdown("**Użytkownik:** Administrator 👨‍💼")
            st.divider()
            if st.button("Wyloguj się", use_container_width=True):
                st.session_state.rola = None
                st.rerun()

        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        
        # --- DASHBOARD (METRYKI) ---
        st.markdown("### 📊 Przegląd Operacyjny")
        dzisiaj = datetime.now().strftime("%Y-%m-%d")
        spakowane_dzisiaj = sum(1 for h in hist_data if h.get('data_pakowania', '').startswith(dzisiaj))
        
        m1, m2, m3 = st.columns(3)
        m1.metric(label="W kolejce do spakowania", value=len(zam_data))
        m2.metric(label="Spakowane dzisiaj", value=spakowane_dzisiaj)
        m3.metric(label="Wszystkie w historii", value=len(hist_data))
        st.divider()
        
        # --- ZAKŁADKI ---
        t1, t2 = st.tabs(["➕ Nowe Zlecenie", "🗄️ Baza Historyczna"])

        with t1:
            col_form, col_pusty = st.columns([2, 1])
            with col_form:
                with st.form("add_form", clear_on_submit=True):
                    st.markdown("#### Utwórz nowe zlecenie kompletacji")
                    nr = st.text_input("Indeks / Numer zamówienia", placeholder="np. ZAM/2026/04/16-01")
                    co = st.text_area("Specyfikacja (co spakować)", placeholder="Wprowadź listę produktów...")
                    
                    if st.form_submit_button("PRZEKAŻ NA MAGAZYN ➔", type="primary"):
                        if nr and co:
                            if len(zam_data) > 0 and zam_data[-1]['nr'] == nr:
                                st.toast("Zlecenie o tym numerze zostało przed chwilą dodane!", icon="⚠️")
                            else:
                                zam_data.append({"id": str(uuid.uuid4()), "nr": nr, "co": co})
                                save_data(ZAM_FILE, zam_data)
                                st.toast(f"Pomyślnie dodano: {nr}", icon="✅")
                                st.rerun() 
                        else:
                            st.toast("Wypełnij wszystkie pola formularza.", icon="❗️")

        with t2:
            st.markdown("#### Dziennik operacji")
            if not hist_data:
                st.info("Brak wpisów w dzienniku.")
            else:
                for h in hist_data:
                    with st.expander(f"ZAM: {h['nr']}  |  Wykonano: {h.get('data_pakowania', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        col_info.markdown(f"**Szczegóły zlecenia:**<br>{h['co']}", unsafe_allow_html=True)
                        if col_action.button("Przywróć", key=f"boss_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.toast("Zlecenie cofnięte na produkcję.", icon="🔄")
                            st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚙️ Zaawansowana administracja rekordami (Tabela)"):
                    edited_hist = st.data_editor(hist_data, num_rows="dynamic", use_container_width=True)
                    if st.button("Zapisz zmiany w bazie"):
                        save_data(HIST_FILE, edited_hist)
                        st.toast("Zaktualizowano bazę danych.", icon="💾")

    # ==========================================
    #           TERMINAL PRACOWNIKA (KDS)
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        
        # CSS ukrywający menu, stopkę ORAZ całkowicie wyłączający przycisk paska bocznego
        st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} 
            header {visibility: hidden;} 
            footer {visibility: hidden;} 
            [data-testid="collapsedControl"] {display: none !important;} 
        </style>
        """, unsafe_allow_html=True)
        
        # Nawigacja pracownika
        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1f77b4; margin-top: -15px;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież", use_container_width=True): st.rerun()
        if c3.button("Wyloguj", use_container_width=True): 
            st.session_state.rola = None
            st.rerun()

        tab_kds, tab_hist = st.tabs(["📦 AKTYWNE ZLECENIA", "🕒 OSTATNIE OPERACJE"])

        # EKRAN GŁÓWNY PAKOWNI
        with tab_kds:
            zam = load_data(ZAM_FILE)
            if not zam:
                st.markdown("""
                <div style='text-align: center; padding: 100px 0;'>
                    <h1 style='font-size: 50px; color: #ccc;'>Brak aktywnych zleceń</h1>
                    <p style='color: #888;'>Kolejka jest pusta. Oczekuj na nowe zadania.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                cols = st.columns(3)
                for i, z in enumerate(zam):
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style='text-align:center;'>
                                <div style='color: #666; font-size: 14px; text-transform: uppercase;'>Zlecenie Nr</div>
                                <div style='font-size: 55px; font-weight: 900; line-height: 1.1; margin-bottom: 10px;'>{z['nr']}</div>
                                <hr style='margin: 10px 0; border: 1px dashed #eee;'>
                                <div style='font-size: 20px; font-weight: bold; margin-bottom: 25px; color: #333;'>{z['co']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("ZAKOŃCZ ZLECENIE", key=f"kds_{z['id']}", use_container_width=True, type="primary"):
                                move_to_history(z['id'])
                                st.toast(f"Spakowano: {z['nr']}", icon="✔️")
                                st.rerun()

        # EKRAN HISTORII (MOŻLIWOŚĆ COFNIĘCIA)
        with tab_hist:
            hist = load_data(HIST_FILE)[:15] 
            if not hist:
                st.info("Brak historii z dzisiejszej zmiany.")
            else:
                for h in hist:
                    with st.expander(f"✔️ ZAM: {h['nr']}  |  {h.get('data_pakowania', '')}"):
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"**Zawartość:** {h['co']}")
                        if col2.button("Cofnij zlecenia", key=f"w_undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.toast(f"Cofnięto zamówienie {h['nr']}", icon="↩️")
                            st.rerun()
