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
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        
        # Zakładki nawigacyjne
        t1, t2 = st.tabs(["➕ Dodaj Zamówienie", "📜 Historia i Edycja"])

        # ZAKŁADKA 1: DODAWANIE
        with t1:
            with st.form("add", clear_on_submit=True):
                nr = st.text_input("Numer zamówienia", placeholder="np. ZAM/001/2026")
                co = st.text_area("Co spakować", placeholder="np. 2x Kubek czarny, 1x Koszulka M")
                submitted = st.form_submit_button("WYŚLIJ NA PRODUKCJĘ")
                
            # Logika zapisu z zabezpieczeniem przed "dwuklikiem"
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

        # ZAKŁADKA 2: HISTORIA
        with t2:
            st.subheader("Wszystkie spakowane zamówienia")
            hist = load_data(HIST_FILE)
            
            if not hist:
                st.info("Historia jest pusta.")
            else:
                # Interaktywna i edytowalna tabela dla szefa
                edited_hist = st.data_editor(hist, num_rows="dynamic", key="editor", use_container_width=True)
                if st.button("ZAPISZ ZMIANY W TABELI"):
                    save_data(HIST_FILE, edited_hist)
                    st.success("Zmiany zapisane!")
                
                st.divider()
                st.write("Wymuś przywrócenie zamówienia na produkcję:")
                to_restore = st.selectbox("Wybierz zamówienie z historii", 
                                          options=[x['id'] for x in hist],
                                          format_func=lambda x: next(i['nr'] for i in hist if i['id'] == x))
                if st.button("PRZYWRÓĆ WYBRANE"):
                    restore_from_history(to_restore)
                    st.success("Zamówienie wróciło do pakowni!")
                    st.rerun()

    # ==========================================
    #           PANEL PRACOWNIKA (KDS)
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        
        # CSS ukrywający zbędne paski i ulepszający układ (Ekran Kioskowy)
        st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} 
            header {visibility: hidden;} 
            footer {visibility: hidden;} 
            .block-container {padding-top: 1rem; max-width: 95%;}
        </style>
        """, unsafe_allow_html=True)
        
        # Pasek nawigacji górnej
        col_tytul, col_odswiez = st.columns([8, 1])
        col_tytul.markdown("<h1 style='color: #E63946; margin-top: -20px;'>🔴 DO SPAKOWANIA</h1>", unsafe_allow_html=True)
        if col_odswiez.button("🔄 Odśwież", use_container_width=True): 
            st.rerun()

        zam = load_data(ZAM_FILE)
        
        # AKTYWNE ZAMÓWIENIA NA EKRANIE
        if not zam:
            st.markdown("<h1 style='text-align: center; font-size: 60px; margin-top: 100px; color: #4CAF50;'>Brak zamówień. Dobra robota!</h1>", unsafe_allow_html=True)
        else:
            cols = st.columns(3) # Siatka po 3 kafelki
            for i, z in enumerate(zam):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"""
                        <div style='text-align:center;'>
                            <div style='font-size: 65px; font-weight: 900; line-height: 1.1;'>{z['nr']}</div>
                            <div style='font-size: 24px; font-weight: bold; margin-top: 10px; margin-bottom: 25px;'>{z['co']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("🟢 GOTOWE", key=z['id'], use_container_width=True, type="primary"):
                            move_to_history(z['id'])
                            st.rerun()

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # OSTATNIO SPAKOWANE (OPCJA COFNIĘCIA)
        st.subheader("🕒 Ostatnio spakowane (możesz cofnąć)")
        hist = load_data(HIST_FILE)[:5] # Ładuje tylko 5 ostatnich z historii
        
        if hist:
            h_cols = st.columns(len(hist))
            for i, h in enumerate(hist):
                with h_cols[i]:
                    with st.container(border=True):
                        st.write(f"**{h['nr']}**")
                        if st.button("↩️ COFNIJ", key=f"undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
