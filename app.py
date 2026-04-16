import streamlit as st
import json
import os
import uuid
from datetime import datetime, date

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pakownia | System Zarządzania", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- 2. PROFESJONALNY CSS (ENTERPRISE THEME) ---
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
    button[kind="primary"]:hover {
        background-color: #172554 !important; 
        box-shadow: 0 6px 15px rgba(30, 58, 138, 0.3) !important;
    }
    
    div[data-testid="stMetricValue"] { color: #1e3a8a !important; font-weight: 800 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. BAZA DANYCH ---
ZAM_FILE = "zamowienia.json"
HIST_FILE = "historia.json"
DYSPOZYCJE_FILE = "dyspozycje.json"
HIST_DYSPOZYCJI_FILE = "historia_dyspozycji.json"

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

# Logika Zamówień
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
        zam.sort(key=lambda x: x.get('termin', '9999-12-31'))
        hist = [x for x in hist if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

# Logika Dyspozycji (Zadań)
def move_dyspozycja_to_history(dysp_id):
    dyspo = load_data(DYSPOZYCJE_FILE)
    hist = load_data(HIST_DYSPOZYCJI_FILE)
    task = next((x for x in dyspo if x['id'] == dysp_id), None)
    if task:
        task['data_wykonania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, task)
        dyspo = [x for x in dyspo if x['id'] != dysp_id]
        save_data(DYSPOZYCJE_FILE, dyspo)
        save_data(HIST_DYSPOZYCJI_FILE, hist)

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
        
        with st.sidebar:
            st.markdown("**Użytkownik:** Administrator 👨‍💼")
            st.divider()
            if st.button("Wyloguj się", use_container_width=True):
                st.session_state.rola = None
                st.rerun()

        zam_data = load_data(ZAM_FILE)
        hist_data = load_data(HIST_FILE)
        dyspo_data = load_data(DYSPOZYCJE_FILE)
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        
        do_spakowania_dzisiaj = sum(1 for z in zam_data if z.get('termin') == dzisiaj_str or z.get('termin', '9999-12-31') < dzisiaj_str)
        spakowane_dzisiaj = sum(1 for h in hist_data if h.get('data_pakowania', '').startswith(dzisiaj_str))
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="Wszystkie w kolejce", value=len(zam_data))
        m2.metric(label="Wymagane na dzisiaj", value=do_spakowania_dzisiaj)
        m3.metric(label="Spakowane dzisiaj", value=spakowane_dzisiaj)
        m4.metric(label="Aktywne Dyspozycje", value=len(dyspo_data))
        st.divider()
        
        # Zakładki Szefa z dodaną Dyspozycją
        t1, t2, t3 = st.tabs(["➕ Nowe Zlecenie", "🗄️ Baza Historyczna", "📝 Dyspozycje i Zadania"])

        # --- ZAKŁADKA 1: ZAMÓWIENIA ---
        with t1:
            col_form, col_pusty = st.columns([2, 1])
            with col_form:
                with st.form("add_form", clear_on_submit=True):
                    st.markdown("#### Utwórz nowe zlecenie kompletacji")
                    nr = st.text_input("Indeks / Numer zamówienia", placeholder="np. ZAM/2026/04/16-01")
                    termin = st.date_input("Wymagany termin realizacji", value=date.today())
                    co = st.text_area("Specyfikacja (co spakować)", placeholder="Wprowadź listę produktów...")
                    
                    if st.form_submit_button("PRZEKAŻ NA MAGAZYN", type="primary"):
                        if nr and co:
                            if len(zam_data) > 0 and zam_data[-1]['nr'] == nr:
                                st.toast("Zlecenie o tym numerze zostało przed chwilą dodane!", icon="⚠️")
                            else:
                                zam_data.append({
                                    "id": str(uuid.uuid4()), 
                                    "nr": nr, 
                                    "co": co, 
                                    "termin": termin.strftime("%Y-%m-%d")
                                })
                                zam_data.sort(key=lambda x: x.get('termin', '9999-12-31'))
                                save_data(ZAM_FILE, zam_data)
                                st.toast(f"Pomyślnie dodano: {nr}", icon="✅")
                                st.rerun() 
                        else:
                            st.toast("Wypełnij wszystkie pola formularza.", icon="❗️")

        # --- ZAKŁADKA 2: HISTORIA ---
        with t2:
            st.markdown("#### Dziennik operacji (Zamówienia)")
            if not hist_data:
                st.info("Brak wpisów w dzienniku.")
            else:
                for h in hist_data:
                    with st.expander(f"ZAM: {h['nr']}  |  Wykonano: {h.get('data_pakowania', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        col_info.markdown(f"**Szczegóły:**<br>{h['co']}", unsafe_allow_html=True)
                        if col_action.button("Przywróć na produkcję", key=f"boss_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.toast("Zlecenie cofnięte.", icon="🔄")
                            st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚙️ Zaawansowana administracja rekordami"):
                    edited_hist = st.data_editor(hist_data, num_rows="dynamic", use_container_width=True)
                    if st.button("Zapisz zmiany w bazie zamówień"):
                        save_data(HIST_FILE, edited_hist)
                        st.toast("Zaktualizowano.", icon="💾")

        # --- ZAKŁADKA 3: DYSPOZYCJE ---
        with t3:
            col_d1, col_d2 = st.columns([1, 1])
            
            with col_d1:
                with st.form("form_dyspozycja", clear_on_submit=True):
                    st.markdown("#### Dodaj nowe zadanie poboczne")
                    tresc_dysp = st.text_area("Treść zadania / Komunikat dla pracowników", placeholder="np. Posprzątaj stanowisko nr 2, brakuje taśmy...")
                    
                    if st.form_submit_button("Wyślij Dyspozycję", type="primary"):
                        if tresc_dysp:
                            dyspo_data.insert(0, {
                                "id": str(uuid.uuid4()),
                                "tresc": tresc_dysp,
                                "data_dodania": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            save_data(DYSPOZYCJE_FILE, dyspo_data)
                            st.toast("Wysłano dyspozycję na magazyn!", icon="✅")
                            st.rerun()
                        else:
                            st.toast("Wpisz treść dyspozycji.", icon="❗️")
                            
            with col_d2:
                st.markdown("#### Aktywne zadania na magazynie")
                if not dyspo_data:
                    st.info("Brak aktywnych zadań.")
                else:
                    for d in dyspo_data:
                        with st.container(border=True):
                            st.markdown(f"**Nodano:** {d['data_dodania']}<br>{d['tresc']}", unsafe_allow_html=True)
                            if st.button("Usuń (Anuluj)", key=f"del_dysp_{d['id']}"):
                                dyspo_data = [x for x in dyspo_data if x['id'] != d['id']]
                                save_data(DYSPOZYCJE_FILE, dyspo_data)
                                st.rerun()

    # ==========================================
    #           TERMINAL PRACOWNIKA (KDS)
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        
        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież", use_container_width=True): st.rerun()
        if c3.button("Wyloguj", use_container_width=True): 
            st.session_state.rola = None
            st.rerun()

        # Zakładki u pracownika - dodana Tablica Zadań
        tab_kds, tab_dyspo, tab_hist = st.tabs(["📦 AKTYWNE ZLECENIA", "📌 TABLICA ZADAŃ", "🕒 OSTATNIE OPERACJE"])
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")

        # --- ZAKŁADKA 1: PAKOWNIA (ZAMÓWIENIA) ---
        with tab_kds:
            zam = load_data(ZAM_FILE)
            if not zam:
                st.markdown("""
                <div style='text-align: center; padding: 100px 0;'>
                    <h1 style='font-size: 40px; color: #94a3b8;'>Brak aktywnych zleceń</h1>
                    <p style='color: #cbd5e1; font-size: 20px;'>Kolejka jest pusta. Oczekuj na nowe zadania.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                cols = st.columns(3)
                for i, z in enumerate(zam):
                    with cols[i % 3]:
                        with st.container(border=True):
                            termin_zlecenia = z.get('termin', '9999-12-31')
                            if termin_zlecenia < dzisiaj_str:
                                badge_html = f"<div style='background-color: #fee2e2; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⚠️ ZALEGŁE: {termin_zlecenia}</div>"
                            elif termin_zlecenia == dzisiaj_str:
                                badge_html = f"<div style='background-color: #fef3c7; color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⏱️ NA DZISIAJ</div>"
                            else:
                                badge_html = f"<div style='background-color: #f1f5f9; color: #64748b; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 700; display: inline-block; margin-bottom: 10px;'>📅 Termin: {termin_zlecenia}</div>"

                            st.markdown(f"""
                            <div style='text-align:center;'>
                                {badge_html}
                                <div style='color: #64748b; font-size: 14px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;'>Zlecenie Nr</div>
                                <div style='font-size: 50px; font-weight: 900; line-height: 1.1; margin-bottom: 10px; color: #0f172a;'>{z['nr']}</div>
                                <hr style='margin: 15px 0; border: none; border-top: 1px dashed #cbd5e1;'>
                                <div style='font-size: 20px; font-weight: 600; margin-bottom: 25px; color: #334155;'>{z['co']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("ZAKOŃCZ ZLECENIE", key=f"kds_{z['id']}", use_container_width=True, type="primary"):
                                move_to_history(z['id'])
                                st.toast(f"Spakowano: {z['nr']}", icon="✔️")
                                st.rerun()

        # --- ZAKŁADKA 2: DYSPOZYCJE (ZADANIA) ---
        with tab_dyspo:
            dyspo = load_data(DYSPOZYCJE_FILE)
            if not dyspo:
                st.markdown("""
                <div style='text-align: center; padding: 80px 0;'>
                    <h1 style='font-size: 35px; color: #94a3b8;'>Brak dodatkowych zadań</h1>
                    <p style='color: #cbd5e1; font-size: 18px;'>Wszystkie dyspozycje zostały wykonane.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                d_cols = st.columns(3)
                for i, d in enumerate(dyspo):
                    with d_cols[i % 3]:
                        with st.container(border=True):
                            # Inny wygląd wizualny dla dyspozycji (kolory ostrzegawcze/informacyjne)
                            st.markdown(f"""
                            <div style='background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 15px;'>
                                <div style='color: #b45309; font-size: 12px; font-weight: bold; margin-bottom: 5px;'>📌 DYSPOZYCJA Z: {d.get('data_dodania', '')}</div>
                                <div style='font-size: 18px; font-weight: 600; color: #451a03;'>{d['tresc']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Przycisk ze specjalnym kluczem
                            if st.button("POTWIERDŹ WYKONANIE", key=f"dysp_{d['id']}", use_container_width=True):
                                move_dyspozycja_to_history(d['id'])
                                st.toast("Zadanie odhaczone!", icon="👍")
                                st.rerun()

        # --- ZAKŁADKA 3: HISTORIA ZAMÓWIEŃ ---
        with tab_hist:
            hist = load_data(HIST_FILE)[:15] 
            if not hist:
                st.info("Brak historii z dzisiejszej zmiany.")
            else:
                for h in hist:
                    with st.expander(f"✔️ ZAM: {h['nr']}  |  Wykonano: {h.get('data_pakowania', '')}"):
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"**Zawartość:** {h['co']}")
                        if col2.button("Cofnij zlecenie na ekran", key=f"w_undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.toast(f"Cofnięto zamówienie {h['nr']}", icon="↩️")
                            st.rerun()
