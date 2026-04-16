import streamlit as st
import json
import os
import uuid

# Zmiana layoutu na 'wide' - aplikacja zajmie cały ekran (idealne dla monitorów na produkcji)
st.set_page_config(page_title="System Pakowni", page_icon="📦", layout="wide")

DATA_FILE = "zamowienia.json"

# --- HASŁA DOSTĘPU (Zmień na własne!) ---
HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# --- FUNKCJE BAZY DANYCH ---
def load_orders():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_orders(orders):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=4)

def update_state():
    st.session_state.orders = load_orders()

# --- INICJALIZACJA STANU APLIKACJI ---
if 'orders' not in st.session_state:
    st.session_state.orders = load_orders()

if 'rola' not in st.session_state:
    st.session_state.rola = None

# --- EKRAN LOGOWANIA ---
if st.session_state.rola is None:
    # Wyśrodkowanie logowania mimo szerokiego ekranu
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Logowanie do systemu")
        st.write("Wprowadź hasło, aby uzyskać dostęp do swojego panelu.")
        
        with st.form("formularz_logowania"):
            wpisane_haslo = st.text_input("Hasło", type="password")
            zaloguj_btn = st.form_submit_button("Zaloguj", use_container_width=True)
            
            if zaloguj_btn:
                if wpisane_haslo == HASLO_SZEFA:
                    st.session_state.rola = 'szef'
                    st.rerun()
                elif wpisane_haslo == HASLO_PRACOWNIKA:
                    st.session_state.rola = 'pracownik'
                    st.rerun()
                else:
                    st.error("Błędne hasło! Spróbuj ponownie.")

# --- WIDOKI PO ZALOGOWANIU ---
else:
    # --- PANEL SZEFA ---
    if st.session_state.rola == 'szef':
        # Pasek boczny tylko dla szefa
        st.sidebar.title("Zalogowano jako: Szef 👨‍💼")
        if st.sidebar.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()

        st.title("👨‍💼 Panel Szefa - Dodaj zamówienie")
        
        with st.form("dodaj_zamowienie", clear_on_submit=True):
            nr_zamowienia = st.text_input("Numer zamówienia", placeholder="np. ZAM/001/2026")
            co_spakowac = st.text_area("Co spakować", placeholder="np. 2x Kubek czarny, 1x Koszulka M")
            submit = st.form_submit_button("Przekaż do pakowania")
            
            if submit:
                if nr_zamowienia and co_spakowac:
                    nowe_zamowienie = {
                        "id": str(uuid.uuid4()),
                        "nr": nr_zamowienia,
                        "co": co_spakowac
                    }
                    aktualne_zamowienia = load_orders()
                    aktualne_zamowienia.insert(0, nowe_zamowienie)
                    save_orders(aktualne_zamowienia)
                    update_state()
                    st.success(f"Zamówienie {nr_zamowienia} zostało przekazane na produkcję!")
                else:
                    st.error("Wypełnij oba pola przed dodaniem zamówienia!")
                    
        st.divider()
        aktualne_zamowienia = load_orders()
        st.info(f"📦 Aktualnie w kolejce u pracowników: **{len(aktualne_zamowienia)} paczek**")

    # --- PANEL PRACOWNIKA (CZYSTY EKRAN KIOSKOWY) ---
    elif st.session_state.rola == 'pracownik':
        # Górny pasek: Tytuł po lewej, przyciski po prawej
        col_tytul, col_btn1, col_btn2 = st.columns([6, 1, 1])
        with col_tytul:
            st.title("📦 Ekran Pakowni")
        with col_btn1:
            if st.button("🔄 Odśwież", use_container_width=True):
                update_state()
        with col_btn2:
            if st.button("Wyloguj", use_container_width=True):
                st.session_state.rola = None
                st.rerun()
                
        st.markdown("---")
        
        aktualne_zamowienia = load_orders()
        
        if not aktualne_zamowienia:
            st.success("Brak zamówień do spakowania. Można odpocząć!")
        else:
            # Wyświetlanie zamówień jako wyraźne kafelki na cały ekran
            for z in aktualne_zamowienia:
                with st.container(border=True): # Tworzy widoczną ramkę wokół zamówienia
                    col_info, col_akcja = st.columns([4, 1])
                    
                    with col_info:
                        st.subheader(f"Zamówienie: {z['nr']}")
                        st.write(f"**Do spakowania:** {z['co']}")
                        
                    with col_akcja:
                        st.write("") # Pusty wiersz dla wyśrodkowania w pionie
                        # type="primary" nadaje przyciskowi wyraźny, główny kolor (zazwyczaj czerwony/niebieski w zależności od motywu)
                        if st.button("✅ ZROBIONE", key=z['id'], use_container_width=True, type="primary"):
                            aktualne_zamowienia = [item for item in aktualne_zamowienia if item['id'] != z['id']]
                            save_orders(aktualne_zamowienia)
                            update_state()
                            st.rerun()
