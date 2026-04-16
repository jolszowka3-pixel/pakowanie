import streamlit as st
import json
import os
import uuid
from datetime import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="System Pakowni PRO", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- PLIKI BAZY DANYCH ---
ZAM_FILE = "zamowienia.json"
HIST_FILE = "historia.json"

# --- HASŁA DOSTĘPU (Zmień na własne) ---
HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# --- FUNKCJE OBSŁUGI DANYCH ---
def load_data(file):
    if not os.path.exists(file): return []
    with open(file, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def move_to_history(order_id):
    """Przenosi zamówienie z listy aktywnych do historii."""
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    
    order = next((x for x in zam if x['id'] == order_id), None)
    if order:
        # Zapisujemy datę i godzinę spakowania (bez sekund, dla czystszego widoku)
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order) # Nowe zlecenia trafiają na samą górę historii
        zam = [x for x in zam if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def restore_from_history(order_id):
    """Cofa zamówienie z historii z powrotem na produkcję."""
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    
    order = next((x for x in hist if x['id'] == order_id), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order) # Zwracamy na listę aktywnych
        hist = [x for x in hist if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

# --- INICJALIZACJA SESJI ---
if 'rola' not in st.session_state: 
    st.session_state.rola = None

# --- EKRAN LOGOWANIA ---
if st.session_state.rola is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔐 System Pakowni</h1>", unsafe_allow_html=True)
        with st.form("login"):
            h = st.text_input("Wprowadź hasło dostępu", type="password")
            if st.form_submit_button("ZALOGUJ", use_container_width=True):
                if h == HASLO_SZEFA: 
                    st.session_state.rola = 'szef'
                    st.rerun()
                elif h == HASLO_PRACOWNIKA: 
                    st.session_state.rola = 'pracownik'
                    st.rerun()
                else: 
                    st.error("Błędne hasło!")

# --- WIDOKI PO ZALOGOWANIU ---
else:
    # Wylogowanie w pasku bocznym (wspólne dla obu ról)
    if st.sidebar.button("WYLOGUJ SIĘ", use_container_width=True):
        st.session_state.rola = None
        st.rerun()

    # ==========================================
    #             PANEL SZEFA
    # ==========================================
    if st.session_state.rola == 'szef':
        st.title("👨‍💼 Panel Zarządzania")
        
        # Zakładki nawigacyjne Szefa
        t1, t2 = st.tabs(["➕ Dodaj Zamówienie", "📜 Historia Zamówień"])

        # ZAKŁADKA 1: DODAWANIE
        with t1:
            with st.form("add", clear_on_submit=True):
                nr = st.text_input("Numer zamówienia", placeholder="np. ZAM/001/2026")
                co = st.text_area("Co spakować", placeholder="np. 2x Kubek czarny, 1x Koszulka M")
                submitted = st.form_submit_button("WYŚLIJ NA PRODUKCJĘ")
                
            if submitted:
                if nr and co:
                    d = load_data(ZAM_FILE)
                    if len(d) > 0 and d[-1]['nr'] == nr and d[-1]['co'] == co:
                        st.warning(f"Uwaga: Zamówienie {nr} zostało już przed sekundą wysłane!")
                    else:
                        d.append({"id": str(uuid.uuid4()), "nr": nr, "co": co})
                        save_data(ZAM_FILE, d)
                        st.success(f"Pomyślnie wysłano na produkcję: {nr}")
                else:
                    st.error("Wypełnij oba pola!")

        # ZAKŁADKA 2: HISTORIA SZEFA (Z EXPANDERAMI)
        with t2:
            st.subheader("Wszystkie spakowane zamówienia")
            hist = load_data(HIST_FILE)
            
            if not hist:
                st.info("Historia jest pusta. Żadne zamówienie nie zostało jeszcze spakowane.")
            else:
                # Estetyczna lista rozwijana dla każdego zamówienia
                for h in hist:
                    data_spak = h.get('data_pakowania', 'Brak daty')
                    with st.expander(f"📦 ZAM: {h['nr']}  |  🕒 Spakowano: {data_spak}"):
                        st.markdown(f"**Co zostało spakowane:**<br>{h['co']}", unsafe_allow_html=True)
                        st.write("") # Odstęp
                        if st.button("🔄 PRZYWRÓĆ NA PRODUKCJĘ", key=f"boss_res_{h['id']}", type="primary"):
                            restore_from_history(h['id'])
                            st.success(f"Zamówienie {h['nr']} wróciło do pakowni!")
                            st.rerun()
                
                st.markdown("<br><br>", unsafe_allow_html=True)
                
                # Opcja edycji tekstu schowana w osobnym akordeonie na samym dole
                with st.expander("⚙️ Zaawansowana edycja bazy danych (Tabela)"):
                    st.write("Tutaj możesz poprawić błędy tekstowe w archiwalnych zamówieniach:")
                    edited_hist = st.data_editor(hist, num_rows="dynamic", key="editor", use_container_width=True)
                    if st.button("ZAPISZ ZMIANY W TABELI"):
                        save_data(HIST_FILE, edited_hist)
                        st.success("Zmiany w historii zostały zapisane!")

    # ==========================================
    #           PANEL PRACOWNIKA (KDS)
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        
        st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} 
            header {visibility: hidden;} 
            footer {visibility: hidden;} 
            .block-container {padding-top: 1rem; max-width: 95%;}
        </style>
        """, unsafe_allow_html=True)
        
        # Pasek nawigacji górnej
        col_odswiez, col_puste = st.columns([1, 9])
        if col_odswiez.button("🔄 Odśwież ekran", use_container_width=True): 
            st.rerun()

        # Zakładki nawigacyjne Pracownika
        tab_kds, tab_hist = st.tabs(["🔴 EKRAN PAKOWNI", "🕒 HISTORIA ZAMÓWIEŃ"])

        # ZAKŁADKA 1: EKRAN GŁÓWNY (KDS)
        with tab_kds:
            zam = load_data(ZAM_FILE)
            
            if not zam:
                st.markdown("<h1 style='text-align: center; font-size: 60px; margin-top: 80px; color: #4CAF50;'>Brak zamówień. Dobra robota!</h1>", unsafe_allow_html=True)
            else:
                cols = st.columns(3) # Siatka po 3 kafelki
                for i, z in enumerate(zam):
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style='text-align:center;'>
                                <div style='font-size: 65px; font-weight: 900; line-height: 1.1;'>{z['nr']}</div>
                                <div style='font-size: 24px; font-weight: bold; margin-top: 15px; margin-bottom: 25px;'>{z['co']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("🟢 GOTOWE", key=f"kds_{z['id']}", use_container_width=True, type="primary"):
                                move_to_history(z['id'])
                                st.rerun()

        # ZAKŁADKA 2: HISTORIA PRACOWNIKA (Z EXPANDERAMI)
        with tab_hist:
            st.subheader("Ostatnio spakowane paczki")
            hist = load_data(HIST_FILE)[:15] # Ładuje tylko 15 ostatnich z historii dla pracownika
            
            if not hist:
                st.info("Lista spakowanych zamówień jest pusta.")
            else:
                for h in hist:
                    data_spak = h.get('data_pakowania', 'Brak daty')
                    # Tytuł expandera widoczny od razu
                    with st.expander(f"✅ ZAM: {h['nr']}  |  🕒 Spakowano: {data_spak}"):
                        st.markdown(f"<span style='font-size: 18px;'>**Zawartość paczki:** {h['co']}</span>", unsafe_allow_html=True)
                        st.write("") # Odstęp
                        # Przycisk "Cofnij" widoczny dopiero po rozwinięciu
                        if st.button("↩️ COFNIJ NA EKRAN PAKOWNI", key=f"worker_undo_{h['id']}", type="secondary"):
                            restore_from_history(h['id'])
                            st.rerun()
