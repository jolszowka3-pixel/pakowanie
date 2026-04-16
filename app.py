import streamlit as st
import json
import os
import uuid
from datetime import datetime

# Konfiguracja
st.set_page_config(page_title="System Pakowni PRO", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

ZAM_FILE = "zamowienia.json"
HIST_FILE = "historia.json"

# --- HASŁA ---
HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# --- FUNKCJE DANYCH ---
def load_data(file):
    if not os.path.exists(file): return []
    with open(file, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- LOGIKA PRZENOSZENIA ---
def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    
    order = next((x for x in zam if x['id'] == order_id), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hist.insert(0, order) # Nowe na górę historii
        zam = [x for x in zam if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    
    order = next((x for x in hist if x['id'] == order_id), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order) # Wraca na koniec kolejki
        hist = [x for x in hist if x['id'] != order_id]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

# --- LOGOWANIE ---
if 'rola' not in st.session_state: st.session_state.rola = None

if st.session_state.rola is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔐 System Pakowni</h1>", unsafe_allow_html=True)
        with st.form("login"):
            h = st.text_input("Hasło", type="password")
            if st.form_submit_button("ZALOGUJ", use_container_width=True):
                if h == HASLO_SZEFA: st.session_state.rola = 'szef'; st.rerun()
                elif h == HASLO_PRACOWNIKA: st.session_state.rola = 'pracownik'; st.rerun()
                else: st.error("Błędne hasło")

# --- WIDOKI ---
else:
    # Sidebar dla obu ról (wylogowanie)
    if st.sidebar.button("WYLOGUJ"):
        st.session_state.rola = None
        st.rerun()

    if st.session_state.rola == 'szef':
        st.title("👨‍💼 Panel Zarządzania")
        t1, t2 = st.tabs(["➕ Dodaj Zamówienie", "📜 Historia i Edycja"])

        with t1:
            with st.form("add"):
                nr = st.text_input("Numer zamówienia")
                co = st.text_area("Co spakować")
                if st.form_submit_button("WYŚLIJ NA PRODUKCJĘ"):
                    if nr and co:
                        d = load_data(ZAM_FILE)
                        d.append({"id": str(uuid.uuid4()), "nr": nr, "co": co})
                        save_data(ZAM_FILE, d)
                        st.success("Dodano!")
                        st.rerun()

        with t2:
            st.subheader("Wszystkie spakowane zamówienia")
            hist = load_data(HIST_FILE)
            if not hist:
                st.write("Historia jest pusta.")
            else:
                # Edytowalna tabela dla szefa
                edited_hist = st.data_editor(hist, num_rows="dynamic", key="editor", use_container_width=True)
                if st.button("ZAPISZ ZMIANY W HISTORII"):
                    save_data(HIST_FILE, edited_hist)
                    st.success("Zmiany zapisane!")
                
                st.divider()
                st.write("Przywróć do pakowania (jeśli trzeba ponowić):")
                to_restore = st.selectbox("Wybierz zamówienie do przywrócenia", 
                                        options=[x['id'] for x in hist],
                                        format_func=lambda x: next(i['nr'] for i in hist if i['id'] == x))
                if st.button("PRZYWRÓĆ WYBRANE"):
                    restore_from_history(to_restore)
                    st.rerun()

    elif st.session_state.rola == 'pracownik':
        # Styl KDS
        st.markdown("""<style>#MainMenu, header, footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
        
        col_t, col_r = st.columns([8, 1])
        col_t.markdown("<h1 style='color: #E63946;'>📦 DO SPAKOWANIA</h1>", unsafe_allow_html=True)
        if col_r.button("🔄 Odśwież"): st.rerun()

        zam = load_data(ZAM_FILE)
        if not zam:
            st.info("Brak nowych zleceń.")
        else:
            cols = st.columns(3)
            for i, z in enumerate(zam):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center;'><h1 style='margin:0;'>{z['nr']}</h1><p style='font-size:20px;'>{z['co']}</p></div>", unsafe_allow_html=True)
                        if st.button("🟢 GOTOWE", key=z['id'], use_container_width=True, type="primary"):
                            move_to_history(z['id'])
                            st.rerun()

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.subheader("🕒 Ostatnio spakowane (możesz cofnąć)")
        hist = load_data(HIST_FILE)[:5] # Pokazujemy tylko 5 ostatnich
        
        if hist:
            h_cols = st.columns(len(hist))
            for i, h in enumerate(hist):
                with h_cols[i]:
                    with st.container(border=True):
                        st.write(f"**{h['nr']}**")
                        if st.button("↩️ COFNIJ", key=f"undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
