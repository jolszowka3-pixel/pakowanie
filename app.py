import streamlit as st
import json
import os
import uuid
import base64
import pandas as pd
import time
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pakownia | System Zarządzania", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- AUTO-ODŚWIEŻANIE ---
# Wymusza odświeżenie strony co 30 sekund (30000 ms). Synchronizuje panele bez blokowania API Google.
st_autorefresh(interval=30000, limit=None, key="data_refresher")

# --- 2. PROFESJONALNY CSS (Enterprise Design) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8fafc;
        color: #1e293b;
    }

    .stApp { background-color: #f8fafc; }
    .block-container { padding-top: 2.5rem; max-width: 96%; padding-bottom: 2rem; }

    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;} 
    [data-testid="collapsedControl"] {display: none !important;} 

    /* Nowoczesne Karty */
    div[data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 12px !important;
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01) !important;
        padding: 24px !important;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stVerticalBlock"] div[style*="border"]:hover {
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(15, 23, 42, 0.03) !important;
        transform: translateY(-2px);
    }

    /* Przyciski Granatowe */
    button[kind="primary"] {
        background-color: #1e293b !important; 
        color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #1e293b !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 0.6rem 1.5rem !important;
        width: 100% !important;
        box-shadow: 0 4px 6px -1px rgba(30, 41, 59, 0.15) !important;
        transition: all 0.2s ease;
    }
    button[kind="primary"]:hover { 
        background-color: #334155 !important; 
        box-shadow: 0 6px 12px -2px rgba(30, 41, 59, 0.25) !important;
    }
    button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #475569 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
        transition: all 0.2s ease;
    }
    button[kind="secondary"]:hover {
        background-color: #f8fafc !important;
        border-color: #94a3b8 !important;
        color: #1e293b !important;
    }

    /* Przycisk Drukowania */
    .print-btn {
        display: block;
        width: 100%;
        text-align: center;
        padding: 10px 0;
        background-color: #ffffff;
        color: #1e293b;
        border: 2px solid #1e293b;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        margin-bottom: 12px;
        transition: all 0.2s;
    }
    .print-btn:hover { background-color: #1e293b; color: #ffffff; }

    div[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800 !important; font-size: 2.2rem !important; }
    div[data-testid="stMetricLabel"] { color: #64748b !important; font-weight: 600 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.5px; }
    h1, h2, h3, h4, h5 { color: #0f172a !important; font-weight: 800 !important; letter-spacing: -0.03em !important; }
    button[data-baseweb="tab"] { font-weight: 600 !important; color: #64748b !important; font-size: 0.9rem !important; }
    button[aria-selected="true"] { color: #1e293b !important; border-bottom: 2px solid #1e293b !important; }
    hr { border-color: #e2e8f0 !important; margin: 1.5rem 0 !important; }
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

# ZMIANA: Dodano kolumnę "postep" (postęp pakowania)
SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "ma_etykiete", "typ_wysylki", "postep"],
    "Historia": ["id", "nr", "co", "termin", "ma_etykiete", "data_pakowania", "typ_wysylki", "postep"],
    "Dyspozycje": ["id", "tresc", "data_dodania"],
    "Zwroty": ["id", "nr", "stan", "powod", "notatki", "status", "data", "data_rozpatrzenia"],
    "Etykiety": ["zam_id", "czesc", "dane"]
}

def load_data(sheet_name):
    try:
        # Pamięć 10 sekund - chroni przed limitem Google API
        df = conn.read(worksheet=sheet_name, ttl=10)
        df = df.dropna(how='all') 
        df = df.fillna("") 
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_data(sheet_name, data, clear_cache=True):
    if not data:
        df = pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    else:
        df = pd.DataFrame(data)
    try:
        conn.update(worksheet=sheet_name, data=df)
        if clear_cache:
            st.cache_data.clear() 
    except Exception as e:
        st.error(f"Błąd zapisu do Arkusza Google ({sheet_name}): {e}")

def usun_etykiete(order_id, clear_cache=True):
    etyk_data = load_data(ETYKIETY_FILE)
    nowe_etyk = [e for e in etyk_data if str(e.get('zam_id')) != str(order_id)]
    if len(nowe_etyk) != len(etyk_data):
        save_data(ETYKIETY_FILE, nowe_etyk, clear_cache=clear_cache)

def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    etyk_data = load_data(ETYKIETY_FILE)
    
    order = next((x for x in zam if str(x.get('id')) == str(order_id)), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order)
        zam = [x for x in zam if str(x.get('id')) != str(order_id)]
        nowe_etyk = [e for e in etyk_data if str(e.get('zam_id')) != str(order_id)]
        
        save_data(ZAM_FILE, zam, clear_cache=False)
        save_data(HIST_FILE, hist, clear_cache=False)
        if len(nowe_etyk) != len(etyk_data):
            save_data(ETYKIETY_FILE, nowe_etyk, clear_cache=False)
            
        st.cache_data.clear()
        time.sleep(0.5)

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in hist if str(x.get('id')) == str(order_id)), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        order['ma_etykiete'] = "False" 
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        hist = [x for x in hist if str(x.get('id')) != str(order_id)]
        
        save_data(ZAM_FILE, zam, clear_cache=False)
        save_data(HIST_FILE, hist, clear_cache=False)
        st.cache_data.clear()
        time.sleep(0.5)

def move_dyspozycja_to_history(dysp_id):
    dyspo = load_data(DYSPOZYCJE_FILE)
    dyspo = [x for x in dyspo if str(x.get('id')) != str(dysp_id)]
    save_data(DYSPOZYCJE_FILE, dyspo, clear_cache=False)
    st.cache_data.clear()
    time.sleep(0.5)

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

else:
    # Ładowanie danych
    zam_data = load_data(ZAM_FILE)
    hist_data = load_data(HIST_FILE)
    dyspo_data = load_data(DYSPOZYCJE_FILE)
    zwroty_data = load_data(ZWROTY_FILE)

    # --- PANEL ADMINISTRATORA ---
    if st.session_state.rola == 'szef':
        c1, c2, c3, c4 = st.columns([5, 2, 1.5, 1.5])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>PANEL SZEFA</h2>", unsafe_allow_html=True)
        c2.markdown("<div style='text-align: right; margin-top: 5px;'><b>Użytkownik:</b> Administrator 👨‍💼</div>", unsafe_allow_html=True)
        
        if c3.button("🔄 Odśwież", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        if c4.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()
        st.divider()

        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        
        do_spakowania_dzisiaj = sum(1 for z in zam_data if str(z.get('termin', '9999-12-31')) <= dzisiaj_str)
        spakowane_dzisiaj = sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str))
        oczekujace_zwroty = sum(1 for z in zwroty_data if str(z.get('status')) == 'Nowy')
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="Wszystkie w kolejce", value=len(zam_data))
        m2.metric(label="Wymagane na dzisiaj", value=do_spakowania_dzisiaj)
        m3.metric(label="Spakowane dzisiaj", value=spakowane_dzisiaj)
        if oczekujace_zwroty > 0:
            m4.markdown(f"**Oczekujące zwroty**<br><span style='font-size:2rem; font-weight:800; color:#ef4444;'>{oczekujace_zwroty} ⚠️</span>", unsafe_allow_html=True)
        else:
            m4.metric(label="Oczekujące zwroty", value=oczekujace_zwroty)
        st.divider()
        
        t1, t2, t3, t4, t5 = st.tabs(["➕ Nowe Zlecenie", "📦 Aktywne na Produkcji", "🗄️ Baza Historyczna", "📝 Zadania", "↩️ Zwroty i Reklamacje"])

        with t1:
            col_form, col_pusty = st.columns([2, 1])
            with col_form:
                with st.form("add_form", clear_on_submit=True):
                    st.markdown("#### Utwórz nowe zlecenie kompletacji")
                    nr = st.text_input("Indeks / Numer zamówienia")
                    termin = st.date_input("Wymagany termin realizacji", value=date.today())
                    typ_wysylki = st.radio("Rodzaj dostawy", ["Kurier (Internet)", "Bezpośrednio do klienta"], horizontal=True)
                    
                    st.caption("Wpisz każdy produkt w osobnej linii, aby stworzyć listę dla pracownika:")
                    co = st.text_area("Specyfikacja (co spakować)")
                    
                    plik_etykiety = st.file_uploader("Załącz list przewozowy / etykietę (PDF)", type=["pdf"])
                    if st.form_submit_button("PRZEKAŻ NA MAGAZYN", type="primary"):
                        if nr and co:
                            if len(zam_data) > 0 and str(zam_data[-1].get('nr')) == str(nr):
                                st.toast("Zlecenie o tym numerze zostało przed chwilą dodane!", icon="⚠️")
                            else:
                                new_id = str(uuid.uuid4())
                                if plik_etykiety is not None:
                                    pdf_b64 = base64.b64encode(plik_etykiety.read()).decode('utf-8')
                                    chunk_size = 45000 
                                    etyk_baza = load_data(ETYKIETY_FILE)
                                    for idx, i in enumerate(range(0, len(pdf_b64), chunk_size)):
                                        chunk = pdf_b64[i:i+chunk_size]
                                        etyk_baza.append({"zam_id": new_id, "czesc": idx, "dane": chunk})
                                    save_data(ETYKIETY_FILE, etyk_baza, clear_cache=False)
                                
                                zam_data.append({
                                    "id": new_id, 
                                    "nr": nr, 
                                    "co": co, 
                                    "termin": termin.strftime("%Y-%m-%d"), 
                                    "ma_etykiete": "True" if plik_etykiety else "False",
                                    "typ_wysylki": typ_wysylki,
                                    "postep": "[]" # Inicjalizacja pustego postępu
                                })
                                zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                                save_data(ZAM_FILE, zam_data, clear_cache=False)
                                st.cache_data.clear()
                                time.sleep(0.5)
                                st.toast(f"Pomyślnie dodano: {nr}", icon="✅")
                                st.rerun() 
                        else: st.toast("Wypełnij wymagane pola formularza.", icon="❗️")

        with t2:
            st.markdown("#### Zlecenia w trakcie realizacji przez pakownię")
            if not zam_data: st.info("Obecnie pracownicy nie mają żadnych aktywnych zleceń.")
            else:
                for z in zam_data:
                    with st.expander(f"ZAM: {z['nr']}  |  Wymagany termin: {z.get('termin', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        
                        # ZMIANA: Wizualizacja statusu pakowania dla Szefa
                        linie = [l.strip() for l in str(z.get('co', '')).split('\n') if l.strip()]
                        try:
                            postep = json.loads(str(z.get('postep', '[]')))
                            if not isinstance(postep, list): postep = []
                        except: postep = []
                        while len(postep) < len(linie): postep.append(False)
                        
                        co_html = ""
                        for idx, linia in enumerate(linie):
                            znak = "✅" if postep[idx] else "⏳"
                            co_html += f"<div style='margin-bottom: 4px;'>{znak} {linia}</div>"
                        
                        info_text = f"**Dostawa:** {z.get('typ_wysylki', 'Brak danych')}<br><br>**Postęp kompletacji:**<br>{co_html}"
                        if str(z.get('ma_etykiete')) == "True": info_text += "<br><span style='color:#1e3a8a;'>📄 Etykieta w chmurze gotowa</span>"
                        
                        col_info.markdown(info_text, unsafe_allow_html=True)
                        if col_action.button("Wycofaj (Usuń)", key=f"boss_cancel_{z['id']}", use_container_width=True):
                            nowe_zam = [x for x in zam_data if str(x.get('id')) != str(z['id'])]
                            save_data(ZAM_FILE, nowe_zam, clear_cache=False)
                            usun_etykiete(z['id'], clear_cache=False) 
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()

        with t3:
            st.markdown("#### Dziennik operacji (Zamówienia)")
            if not hist_data: st.info("Brak wpisów w dzienniku.")
            else:
                for h in hist_data:
                    with st.expander(f"✔️ ZAM: {h.get('nr')}  |  Wykonano: {h.get('data_pakowania', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        co_html = str(h.get('co', '')).replace('\n', '<br>')
                        col_info.markdown(f"**Dostawa:** {h.get('typ_wysylki', 'Brak danych')}<br>**Zawartość:**<br>{co_html}", unsafe_allow_html=True)
                        if col_action.button("Przywróć na produkcję", key=f"boss_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚙️ Zaawansowana administracja rekordami"):
                    edited_hist = st.data_editor(hist_data, num_rows="dynamic", use_container_width=True)
                    if st.button("Zapisz zmiany w bazie zamówień"):
                        save_data(HIST_FILE, edited_hist, clear_cache=False)
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.toast("Zaktualizowano.", icon="💾")

        with t4:
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                with st.form("form_dyspozycja", clear_on_submit=True):
                    st.markdown("#### Dodaj nowe zadanie poboczne")
                    tresc_dysp = st.text_area("Treść zadania")
                    if st.form_submit_button("Wyślij Dyspozycję", type="primary"):
                        if tresc_dysp:
                            dyspo_data.insert(0, {"id": str(uuid.uuid4()), "tresc": tresc_dysp, "data_dodania": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            save_data(DYSPOZYCJE_FILE, dyspo_data, clear_cache=False)
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
            with col_d2:
                st.markdown("#### Aktywne zadania")
                if not dyspo_data: st.info("Brak aktywnych zadań.")
                else:
                    for d in dyspo_data:
                        with st.container(border=True):
                            st.markdown(f"**Wysłano:** {d.get('data_dodania')}<br>{d.get('tresc')}", unsafe_allow_html=True)
                            if st.button("Usuń", key=f"del_dysp_{d['id']}"):
                                save_data(DYSPOZYCJE_FILE, [x for x in dyspo_data if str(x.get('id')) != str(d['id'])], clear_cache=False)
                                st.cache_data.clear()
                                time.sleep(0.5)
                                st.rerun()
                                
        with t5:
            st.markdown("#### Obsługa Zwrotów i Reklamacji (RMA)")
            nowe_zwroty = [z for z in zwroty_data if str(z.get('status')) == 'Nowy']
            stare_zwroty = [z for z in zwroty_data if str(z.get('status')) == 'Rozpatrzony']
            st.markdown("##### 🔴 Oczekujące na Twoją decyzję")
            if not nowe_zwroty: st.success("Wszystkie zwroty zostały rozpatrzone.")
            else:
                for z in nowe_zwroty:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"<span style='color:#ef4444; font-weight:bold; font-size:18px;'>ZAMÓWIENIE NR: {z.get('nr')}</span>", unsafe_allow_html=True)
                            st.write(f"**Zgłoszono:** {z.get('data')} | **Stan:** {z.get('stan')}")
                        with col2:
                            if st.button("Rozpatrzono", key=f"zwr_{z['id']}", use_container_width=True, type="primary"):
                                for item in zwroty_data:
                                    if str(item['id']) == str(z['id']):
                                        item['status'] = 'Rozpatrzony'
                                        item['data_rozpatrzenia'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                save_data(ZWROTY_FILE, zwroty_data, clear_cache=False)
                                st.cache_data.clear()
                                time.sleep(0.5)
                                st.rerun()
            st.divider()
            with st.expander("📁 Archiwum rozwiązanych zwrotów"):
                for z in stare_zwroty: st.markdown(f"**{z.get('nr')}** - Stan: {z.get('stan')}")

    # --- TERMINAL PRACOWNIKA ---
    elif st.session_state.rola == 'pracownik':
        if 'znane_zam' not in st.session_state: st.session_state.znane_zam = {str(z.get('id')) for z in zam_data}
        if 'znane_dysp' not in st.session_state: st.session_state.znane_dysp = {str(d.get('id')) for d in dyspo_data}
        akt_zam_ids = {str(z.get('id')) for z in zam_data}
        akt_dysp_ids = {str(d.get('id')) for d in dyspo_data}
        if (akt_zam_ids - st.session_state.znane_zam) or (akt_dysp_ids - st.session_state.znane_dysp):
            st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
            st.toast("🔔 Nowe zadanie na terminalu!", icon="🔔")
        st.session_state.znane_zam, st.session_state.znane_dysp = akt_zam_ids, akt_dysp_ids

        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież", use_container_width=True): 
            st.cache_data.clear()
            st.rerun()
        if c3.button("Wyloguj", use_container_width=True): 
            st.session_state.rola = None
            st.rerun()

        tab_kds, tab_dyspo, tab_zwroty, tab_hist = st.tabs(["📦 AKTYWNE ZLECENIA", "📌 TABLICA ZADAŃ", "↩️ PRZYJMIJ ZWROT", "🕒 OSTATNIE OPERACJE"])
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")

        with tab_kds:
            if not zam_data: 
                st.markdown("<div style='text-align: center; padding: 100px 0;'><h1 style='color: #94a3b8;'>Brak aktywnych zleceń</h1></div>", unsafe_allow_html=True)
            else:
                tab_kurier, tab_bezposrednio = st.tabs(["📦 WYSYŁKI KURIERSKIE", "🚚 BEZPOŚREDNIO DO KLIENTA"])
                etyk_wszystkie = load_data(ETYKIETY_FILE)
                
                zam_kurier = [z for z in zam_data if "Kurier" in str(z.get('typ_wysylki', ''))]
                zam_wlasna = [z for z in zam_data if "Kurier" not in str(z.get('typ_wysylki', ''))]
                
                # ZAKŁADKA 1: KURIER
                with tab_kurier:
                    if not zam_kurier:
                        st.info("Brak przesyłek kurierskich w kolejce.")
                    else:
                        cols_k = st.columns(3)
                        for i, z in enumerate(zam_kurier):
                            with cols_k[i % 3]:
                                with st.container(border=True):
                                    t_zlec = str(z.get('termin', '9999-12-31'))
                                    if t_zlec < dzisiaj_str: badge = f"<div style='background-color: #fee2e2; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⚠️ ZALEGŁE: {t_zlec}</div>"
                                    elif t_zlec == dzisiaj_str: badge = f"<div style='background-color: #fef3c7; color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⏱️ NA DZISIAJ</div>"
                                    else: badge = f"<div style='background-color: #f1f5f9; color: #64748b; padding: 4px 10px; border-radius: 6px; font-weight: 700; display: inline-block; margin-bottom: 10px;'>📅 Termin: {t_zlec}</div>"
                                    
                                    typ_w = str(z.get('typ_wysylki', 'Brak danych'))
                                    if "Kurier" in typ_w: badge_typ = f"<div style='background-color: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px; margin-left: 8px;'>📦 KURIER</div>"
                                    else: badge_typ = ""

                                    st.markdown(f"<div style='text-align:center;'>{badge}{badge_typ}<div style='color: #64748b; font-size: 14px; font-weight: bold;'>Zlecenie Nr</div><div style='font-size: 50px; font-weight: 900; line-height: 1.1; margin-bottom: 10px;'>{z.get('nr')}</div><hr style='margin: 15px 0; border-top: 1px dashed #cbd5e1;'></div>", unsafe_allow_html=True)
                                    
                                    # ZMIANA: Checkboxy postępu (KURIER)
                                    st.markdown("<div style='color: #64748b; font-size: 12px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase;'>Do spakowania:</div>", unsafe_allow_html=True)
                                    linie = [l.strip() for l in str(z.get('co', '')).split('\n') if l.strip()]
                                    
                                    try:
                                        postep = json.loads(str(z.get('postep', '[]')))
                                        if not isinstance(postep, list): postep = []
                                    except: postep = []
                                    while len(postep) < len(linie): postep.append(False)
                                    
                                    nowy_postep = []
                                    for idx, linia in enumerate(linie):
                                        zaznaczone = st.checkbox(linia, value=postep[idx], key=f"chk_k_{z['id']}_{idx}")
                                        nowy_postep.append(zaznaczone)
                                        
                                    st.write("<br>", unsafe_allow_html=True)
                                    
                                    if st.button("💾 ZAPISZ POSTĘP", key=f"prog_k_{z['id']}", use_container_width=True, type="secondary"):
                                        for zam in zam_data:
                                            if zam['id'] == z['id']:
                                                zam['postep'] = json.dumps(nowy_postep)
                                        save_data(ZAM_FILE, zam_data, clear_cache=False)
                                        st.cache_data.clear()
                                        time.sleep(0.5)
                                        st.rerun()
                                    
                                    kawalki = [e for e in etyk_wszystkie if str(e.get('zam_id')) == str(z['id'])]
                                    if kawalki:
                                        kawalki.sort(key=lambda x: int(x.get('czesc', 0)))
                                        pdf_b64 = "".join([str(e.get('dane', '')) for e in kawalki])
                                        html_code = f"<html><body><button style='width: 100%; padding: 0.5rem; background: #f8fafc; color: #1e3a8a; border: 2px solid #1e3a8a; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; height: 45px;' onclick='printPDF()'>🖨️ DRUKUJ ETYKIETĘ</button><script>function printPDF() {{ const b64 = '{pdf_b64}'; const byteCharacters = atob(b64); const byteNumbers = new Array(byteCharacters.length); for (let i = 0; i < byteCharacters.length; i++) {{ byteNumbers[i] = byteCharacters.charCodeAt(i); }} const byteArray = new Uint8Array(byteNumbers); const blob = new Blob([byteArray], {{type: 'application/pdf'}}); const blobUrl = URL.createObjectURL(blob); const printFrame = document.createElement('iframe'); printFrame.style.display = 'none'; printFrame.src = blobUrl; document.body.appendChild(printFrame); printFrame.onload = function() {{ setTimeout(function() {{ try {{ printFrame.contentWindow.focus(); printFrame.contentWindow.print(); }} catch (e) {{ window.open(blobUrl, '_blank'); }} }}, 250); }}; }}</script></body></html>"
                                        components.html(html_code, height=55)
                                        
                                    if st.button("ZAKOŃCZ ZLECENIE", key=f"kds_k_{z['id']}", use_container_width=True, type="primary"):
                                        move_to_history(z['id'])
                                        st.rerun()

                # ZAKŁADKA 2: DOSTAWA WŁASNA
                with tab_bezposrednio:
                    if not zam_wlasna:
                        st.info("Brak dostaw bezpośrednich w kolejce.")
                    else:
                        cols_w = st.columns(3)
                        for i, z in enumerate(zam_wlasna):
                            with cols_w[i % 3]:
                                with st.container(border=True):
                                    t_zlec = str(z.get('termin', '9999-12-31'))
                                    if t_zlec < dzisiaj_str: badge = f"<div style='background-color: #fee2e2; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⚠️ ZALEGŁE: {t_zlec}</div>"
                                    elif t_zlec == dzisiaj_str: badge = f"<div style='background-color: #fef3c7; color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⏱️ NA DZISIAJ</div>"
                                    else: badge = f"<div style='background-color: #f1f5f9; color: #64748b; padding: 4px 10px; border-radius: 6px; font-weight: 700; display: inline-block; margin-bottom: 10px;'>📅 Termin: {t_zlec}</div>"
                                    
                                    typ_w = str(z.get('typ_wysylki', 'Brak danych'))
                                    if "Bezpośrednio" in typ_w: badge_typ = f"<div style='background-color: #f3e8ff; color: #6b21a8; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px; margin-left: 8px;'>🚚 BEZPOŚREDNIO</div>"
                                    else: badge_typ = ""

                                    st.markdown(f"<div style='text-align:center;'>{badge}{badge_typ}<div style='color: #64748b; font-size: 14px; font-weight: bold;'>Zlecenie Nr</div><div style='font-size: 50px; font-weight: 900; line-height: 1.1; margin-bottom: 10px;'>{z.get('nr')}</div><hr style='margin: 15px 0; border-top: 1px dashed #cbd5e1;'></div>", unsafe_allow_html=True)
                                    
                                    # ZMIANA: Checkboxy postępu (BEZPOŚREDNIO)
                                    st.markdown("<div style='color: #64748b; font-size: 12px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase;'>Do spakowania:</div>", unsafe_allow_html=True)
                                    linie = [l.strip() for l in str(z.get('co', '')).split('\n') if l.strip()]
                                    
                                    try:
                                        postep = json.loads(str(z.get('postep', '[]')))
                                        if not isinstance(postep, list): postep = []
                                    except: postep = []
                                    while len(postep) < len(linie): postep.append(False)
                                    
                                    nowy_postep = []
                                    for idx, linia in enumerate(linie):
                                        zaznaczone = st.checkbox(linia, value=postep[idx], key=f"chk_w_{z['id']}_{idx}")
                                        nowy_postep.append(zaznaczone)
                                        
                                    st.write("<br>", unsafe_allow_html=True)
                                    
                                    if st.button("💾 ZAPISZ POSTĘP", key=f"prog_w_{z['id']}", use_container_width=True, type="secondary"):
                                        for zam in zam_data:
                                            if zam['id'] == z['id']:
                                                zam['postep'] = json.dumps(nowy_postep)
                                        save_data(ZAM_FILE, zam_data, clear_cache=False)
                                        st.cache_data.clear()
                                        time.sleep(0.5)
                                        st.rerun()

                                    kawalki = [e for e in etyk_wszystkie if str(e.get('zam_id')) == str(z['id'])]
                                    if kawalki:
                                        kawalki.sort(key=lambda x: int(x.get('czesc', 0)))
                                        pdf_b64 = "".join([str(e.get('dane', '')) for e in kawalki])
                                        html_code = f"<html><body><button style='width: 100%; padding: 0.5rem; background: #f8fafc; color: #1e3a8a; border: 2px solid #1e3a8a; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; height: 45px;' onclick='printPDF()'>🖨️ DRUKUJ ETYKIETĘ</button><script>function printPDF() {{ const b64 = '{pdf_b64}'; const byteCharacters = atob(b64); const byteNumbers = new Array(byteCharacters.length); for (let i = 0; i < byteCharacters.length; i++) {{ byteNumbers[i] = byteCharacters.charCodeAt(i); }} const byteArray = new Uint8Array(byteNumbers); const blob = new Blob([byteArray], {{type: 'application/pdf'}}); const blobUrl = URL.createObjectURL(blob); const printFrame = document.createElement('iframe'); printFrame.style.display = 'none'; printFrame.src = blobUrl; document.body.appendChild(printFrame); printFrame.onload = function() {{ setTimeout(function() {{ try {{ printFrame.contentWindow.focus(); printFrame.contentWindow.print(); }} catch (e) {{ window.open(blobUrl, '_blank'); }} }}, 250); }}; }}</script></body></html>"
                                        components.html(html_code, height=55)
                                        
                                    if st.button("ZAKOŃCZ ZLECENIE", key=f"kds_w_{z['id']}", use_container_width=True, type="primary"):
                                        move_to_history(z['id'])
                                        st.rerun()

        with tab_dyspo:
            if not dyspo_data: st.markdown("<div style='text-align: center; padding: 80px 0;'><h1 style='color: #94a3b8;'>Brak dodatkowych zadań</h1></div>", unsafe_allow_html=True)
            else:
                d_cols = st.columns(3)
                for i, d in enumerate(dyspo_data):
                    with d_cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"<div style='background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 15px;'><div style='color: #b45309; font-size: 12px; font-weight: bold;'>📌 DYSPOZYCJA Z: {d.get('data_dodania', '')}</div><div style='font-size: 18px; font-weight: 600;'>{d.get('tresc')}</div></div>", unsafe_allow_html=True)
                            if st.button("POTWIERDŹ WYKONANIE", key=f"dysp_{d['id']}", use_container_width=True):
                                move_dyspozycja_to_history(d['id'])
                                st.rerun()

        with tab_zwroty:
            st.markdown("### Wprowadź paczkę zwrotną do systemu")
            col1, _ = st.columns([1, 1])
            with col1:
                with st.form("formularz_zwrotu", clear_on_submit=True):
                    nr_zwr = st.text_input("Numer zamówienia")
                    stan_zwr = st.selectbox("Stan", ["Pełnowartościowy", "Uszkodzony"])
                    powod_zwr = st.selectbox("Powód", ["Brak", "Odstąpienie 14 dni", "Reklamacja"])
                    notatki_zwr = st.text_area("Uwagi")
                    if st.form_submit_button("ZAREJESTRUJ ZWROT", type="primary"):
                        if nr_zwr:
                            zwroty_data.insert(0, {"id": str(uuid.uuid4()), "nr": nr_zwr, "stan": stan_zwr, "powod": powod_zwr, "notatki": notatki_zwr, "status": "Nowy", "data": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            save_data(ZWROTY_FILE, zwroty_data, clear_cache=False)
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.toast("Zarejestrowano!", icon="✅")
                            st.rerun()
                        else: st.error("Podaj numer.")

        with tab_hist:
            hist_lim = hist_data[:15] 
            if not hist_lim: st.info("Brak historii.")
            else:
                for h in hist_lim:
                    with st.expander(f"✔️ ZAM: {h.get('nr')} | {h.get('data_pakowania', '')}"):
                        c1, c2 = st.columns([3, 1])
                        co_html = str(h.get('co', '')).replace('\n', '<br>')
                        c1.markdown(f"**Wysyłka:** {h.get('typ_wysylki', 'Brak danych')}<br>**Zawartość:**<br>{co_html}", unsafe_allow_html=True)
                        if c2.button("Cofnij", key=f"w_undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
