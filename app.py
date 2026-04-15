import streamlit as st
import json
import os
import uuid

# Konfiguracja strony
st.set_page_config(page_title="System Pakowni", page_icon="📦", layout="centered")

DATA_FILE = "zamowienia.json"

# Funkcje do obsługi danych (zapis/odczyt z pliku JSON)
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

# Inicjalizacja stanu aplikacji
if 'orders' not in st.session_state:
    st.session_state.orders = load_orders()

def update_state():
    st.session_state.orders = load_orders()

# Pasek boczny do nawigacji
st.sidebar.title("Nawigacja")
widok = st.sidebar.radio("Wybierz panel:", ["Panel Szefa (Dodawanie)", "Panel Pracownika (Pakownia)"])

if widok == "Panel Szefa (Dodawanie)":
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

elif widok == "Panel Pracownika (Pakownia)":
    st.title("📦 Panel Pakowni")
    
    # Przycisk do ręcznego odświeżania listy przez pracownika
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Odśwież listę"):
            update_state()
    
    aktualne_zamowienia = load_orders()
    
    if not aktualne_zamowienia:
        st.info("Brak zamówień do spakowania. Czekamy na nowe zlecenia!")
    else:
        for z in aktualne_zamowienia:
            with st.container():
                st.subheader(f"Numer: {z['nr']}")
                st.write(f"**Zawartość:** {z['co']}")
                
                # Unikalny klucz dla przycisku na podstawie ID zamówienia
                if st.button(f"✓ Zrobione (Spakowane)", key=z['id']):
                    aktualne_zamowienia = [item for item in aktualne_zamowienia if item['id'] != z['id']]
                    save_orders(aktualne_zamowienia)
                    update_state()
                    st.rerun()
                st.divider()
