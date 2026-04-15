import streamlit as st
import json
import os
import uuid

# Konfiguracja strony
st.set_page_config(page_title="System Pakowni", page_icon="📦", layout="centered")

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

# Zmienna przechowująca informację, kto jest zalogowany (None, 'szef' lub 'pracownik')
if 'rola' not in st.session_state:
    st.session_state.rola = None

# --- EKRAN LOGOWANIA ---
if st.session_state.rola is None:
    st.title("🔐 Logowanie do systemu")
    st.write("Wprowadź hasło, aby uzyskać dostęp do swojego panelu.")
    
    with st.form("formularz_logowania"):
        wpisane_haslo = st.text_input("Hasło", type="password")
        zaloguj_btn = st.form_submit_button("Zaloguj")
        
        if zaloguj_btn:
            if wpisane_haslo == HASLO_SZEFA:
                st.session_state.rola = 'szef'
                st.rerun() # Przeładowuje stronę po zalogowaniu
            elif wpisane_haslo == HASLO_PRACOWNIKA:
                st.session_state.rola = 'pracownik'
                st.rerun()
            else:
                st.error("Błędne hasło! Spróbuj ponownie.")

# --- WIDOKI PO ZALOGOWANIU ---
else:
    # PASEK BOCZNY - PRZYCISK WYLOGOWANIA
    st.sidebar.title(f"Zalogowano jako: {'Szef 👨‍💼' if st.session_state.rola == 'szef' else 'Pracownik 📦'}")
    if st.sidebar.button("Wyloguj się"):
        st.session_state.rola = None
        st.rerun()

    # --- PANEL SZEFA ---
    if st.session_state.rola == 'szef':
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
        st.subheader("Aktualnie w kolejce u pracowników:")
        aktualne_zamowienia = load_orders()
        st.write(f"Liczba paczek do spakowania: **{len(aktualne_zamowienia)}**")

    # --- PANEL PRACOWNIKA ---
    elif st.session_state.rola == 'pracownik':
        st.title("📦 Panel Pakowni")
        
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Odśwież listę"):
                update_state()
        
        aktualne_zamowienia = load_orders()
        
        if not aktualne_zamowienia:
            st.success("Brak zamówień do spakowania. Dobra robota, możecie odpocząć!")
        else:
            for z in aktualne_zamowienia:
                with st.container():
                    st.subheader(f"Numer: {z['nr']}")
                    st.write(f"**Zawartość:** {z['co']}")
                    
                    if st.button(f"✓ Zrobione (Spakowane)", key=z['id']):
                        aktualne_zamowienia = [item for item in aktualne_zamowienia if item['id'] != z['id']]
                        save_orders(aktualne_zamowienia)
                        update_state()
                        st.rerun()
                    st.divider()
