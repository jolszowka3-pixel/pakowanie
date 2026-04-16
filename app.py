import streamlit as st
import json
import os
import uuid

# Konfiguracja: szeroki ekran i domyślnie schowany pasek boczny (dla czystości ekranu)
st.set_page_config(page_title="System Pakowni", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

DATA_FILE = "zamowienia.json"

# --- HASŁA DOSTĘPU ---
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

if 'orders' not in st.session_state:
    st.session_state.orders = load_orders()

if 'rola' not in st.session_state:
    st.session_state.rola = None

# --- EKRAN LOGOWANIA ---
if st.session_state.rola is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔐 Kiosk Pakowni</h1>", unsafe_allow_html=True)
        with st.form("formularz_logowania"):
            wpisane_haslo = st.text_input("Podaj kod dostępu", type="password")
            zaloguj_btn = st.form_submit_button("WEJDŹ", use_container_width=True)
            
            if zaloguj_btn:
                if wpisane_haslo == HASLO_SZEFA:
                    st.session_state.rola = 'szef'
                    st.rerun()
                elif wpisane_haslo == HASLO_PRACOWNIKA:
                    st.session_state.rola = 'pracownik'
                    st.rerun()
                else:
                    st.error("Błędny kod!")

# --- WIDOKI PO ZALOGOWANIU ---
else:
    # --- PANEL SZEFA ---
    if st.session_state.rola == 'szef':
        st.sidebar.title("Zalogowano: Szef 👨‍💼")
        if st.sidebar.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()

        st.title("👨‍💼 Panel Szefa - Dodawanie")
        
        with st.form("dodaj_zamowienie", clear_on_submit=True):
            nr_zamowienia = st.text_input("Numer zamówienia", placeholder="np. 001")
            co_spakowac = st.text_area("Co spakować", placeholder="np. 2x Kubek czarny, 1x Koszulka M")
            submit = st.form_submit_button("WŚLIJ NA EKRAN ➔")
            
            if submit:
                if nr_zamowienia and co_spakowac:
                    nowe_zamowienie = {
                        "id": str(uuid.uuid4()),
                        "nr": nr_zamowienia,
                        "co": co_spakowac
                    }
                    aktualne_zamowienia = load_orders()
                    # Dodajemy na koniec listy, żeby stare zlecenia były od góry
                    aktualne_zamowienia.append(nowe_zamowienie)
                    save_orders(aktualne_zamowienia)
                    update_state()
                    st.success(f"Wysłano: {nr_zamowienia}")
                else:
                    st.error("Wypełnij oba pola!")
                    
        aktualne_zamowienia = load_orders()
        st.info(f"📦 Aktualnie na ekranie u pracowników: **{len(aktualne_zamowienia)} zlec.**")

    # --- PANEL PRACOWNIKA (STYL MCDONALD'S KDS) ---
    elif st.session_state.rola == 'pracownik':
        
        # Wstrzyknięcie CSS usuwającego marginesy i górne paski Streamlita
        st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .block-container {padding-top: 1rem; max-width: 95%;}
        </style>
        """, unsafe_allow_html=True)

        # Dyskretny pasek nawigacji na samej górze
        col_odswiez, col_puste, col_wyloguj = st.columns([1, 8, 1])
        with col_odswiez:
            if st.button("🔄 Odśwież"):
                update_state()
        with col_wyloguj:
            if st.button("Wyloguj"):
                st.session_state.rola = None
                st.rerun()
                
        st.markdown("<h2 style='text-align: center; margin-top: -20px; color: #E63946;'>🔴 DO SPAKOWANIA 🔴</h2>", unsafe_allow_html=True)
        
        aktualne_zamowienia = load_orders()
        
        if not aktualne_zamowienia:
            st.markdown("<h1 style='text-align: center; font-size: 60px; margin-top: 100px; color: #4CAF50;'>Brak zamówień. Dobra robota!</h1>", unsafe_allow_html=True)
        else:
            # Tworzymy siatkę (3 zlecenia w jednym rzędzie)
            cols = st.columns(3)
            
            for index, z in enumerate(aktualne_zamowienia):
                # Wybiera odpowiednią kolumnę dla zamówienia (0, 1 lub 2)
                col = cols[index % 3] 
                
                with col:
                    with st.container(border=True):
                        # Ogromny numer zamówienia i większy tekst zawartości
                        st.markdown(f"""
                        <div style="text-align: center;">
                            <div style="font-size: 70px; font-weight: 900; line-height: 1;">{z['nr']}</div>
                            <div style="font-size: 24px; font-weight: bold; margin-top: 15px; margin-bottom: 25px;">{z['co']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Wielki zielony przycisk (type="primary" nadaje mu kolor wiodący)
                        if st.button("🟢 GOTOWE", key=z['id'], use_container_width=True, type="primary"):
                            aktualne_zamowienia = [item for item in aktualne_zamowienia if item['id'] != z['id']]
                            save_orders(aktualne_zamowienia)
                            update_state()
                            st.rerun()
                    st.write("") # Dodatkowy odstęp między rzędami
