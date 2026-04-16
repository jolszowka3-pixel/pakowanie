import streamlit as st
import json
import os
import uuid
import base64
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from datetime import datetime, date

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pakownia | System Zarządzania", page_icon="📦", layout="wide", initial_sidebar_state="collapsed")

# --- 2. PROFESJONALNY CSS ---
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
    button[kind="primary"]:hover { background-color: #172554 !important; box-shadow: 0 6px 15px rgba(30, 58, 138, 0.3) !important; }
    div[data-testid="stMetricValue"] { color: #1e3a8a !important; font-weight: 800 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. GOOGLE SHEETS BAZA DANYCH ---
conn = st.connection("gsheets", type=GSheetsConnection)

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# Definicja nagłówków
SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "pdf_base64"],
    "Historia": ["id", "nr", "co", "termin", "pdf_base64", "data_pakowania"],
    "Dyspozycje": ["id", "tresc", "data_dodania"],
    "Zwroty": ["id", "nr", "stan", "powod", "notatki", "status", "data", "data_rozpatrzenia"]
}

def load_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        df = df.dropna(how='all') 
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_data(sheet_name, data):
    if not data:
        df = pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    else:
        df = pd.DataFrame(data)
    try:
        conn.update(worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")

def move_to_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in zam if str(x.get('id')) == str(order_id)), None)
    if order:
        order['data_pakowania'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.insert(0, order)
        zam = [x for x in zam if str(x.get('id')) != str(order_id)]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def restore_from_history(order_id):
    zam = load_data(ZAM_FILE)
    hist = load_data(HIST_FILE)
    order = next((x for x in hist if str(x.get('id')) == str(order_id)), None)
    if order:
        if 'data_pakowania' in order: del order['data_pakowania']
        zam.append(order)
        zam.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
        hist = [x for x in hist if str(x.get('id')) != str(order_id)]
        save_data(ZAM_FILE, zam)
        save_data(HIST_FILE, hist)

def move_dyspozycja_to_history(dysp_id):
    dyspo = load_data(DYSPOZYCJE_FILE)
    dyspo = [x for x in dyspo if str(x.get('id')) != str(dysp_id)]
    save_data(DYSPOZYCJE_FILE, dyspo)

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
        zwroty_data = load_data(ZWROTY_FILE)
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")
        
        st.markdown("<h3 style='color: #1e3a8a;'>📊 Przegląd Operacyjny</h3>", unsafe_allow_html=True)
        
        do_spakowania_dzisiaj = sum(1 for z in zam_data if str(z.get('termin', '9999-12-31')) <= dzisiaj_str)
        spakowane_dzisiaj = sum(1 for h in hist_data if str(h.get('data_pakowania', '')).startswith(dzisiaj_str))
        oczekujace_zwroty = sum(1 for z in zwroty_data if z.get('status') == 'Nowy')
        
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
                    co = st.text_area("Specyfikacja (co spakować)")
                    plik_etykiety = st.file_uploader("Załącz etykietę (PDF)", type=["pdf"])
                    
                    if st.form_submit_button("PRZEKAŻ NA MAGAZYN", type="primary"):
                        if nr and co:
                            pdf_string = ""
                            if plik_etykiety is not None:
                                pdf_string = base64.b64encode(plik_etykiety.read()).decode('utf-8')
                                if len(pdf_string) > 48000:
                                    st.error("Plik za duży dla Arkusza Google.")
                                    st.stop()

                            zam_data.append({
                                "id": str(uuid.uuid4()), "nr": nr, "co": co, 
                                "termin": termin.strftime("%Y-%m-%d"),
                                "pdf_base64": pdf_string
                            })
                            zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                            save_data(ZAM_FILE, zam_data)
                            st.toast(f"Dodano: {nr}", icon="✅")
                            st.rerun() 
                        else:
                            st.toast("Wypełnij wymagane pola.", icon="❗️")

        with t2:
            st.markdown("#### Zlecenia w trakcie realizacji")
            if not zam_data:
                st.info("Brak aktywnych zleceń.")
            else:
                for z in zam_data:
                    with st.expander(f"ZAM: {z['nr']}  |  Termin: {z.get('termin', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        info_text = f"**Co spakować:**<br>{z['co']}"
                        if z.get('pdf_base64'): info_text += "<br><span style='color:#1e3a8a;'>📄 Dołączono etykietę PDF</span>"
                        col_info.markdown(info_text, unsafe_allow_html=True)
                        if col_action.button("Wycofaj (Usuń)", key=f"boss_cancel_{z['id']}", use_container_width=True):
                            zam_data = [x for x in zam_data if str(x.get('id')) != str(z['id'])]
                            save_data(ZAM_FILE, zam_data)
                            st.rerun()

        with t3:
            st.markdown("#### Dziennik operacji")
            if not hist_data:
                st.info("Brak wpisów.")
            else:
                for h in hist_data:
                    with st.expander(f"✔️ ZAM: {h.get('nr')}  |  Spakowano: {h.get('data_pakowania', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        col_info.markdown(f"**Szczegóły:**<br>{h.get('co')}", unsafe_allow_html=True)
                        if col_action.button("Przywróć", key=f"boss_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
                
                with st.expander("⚙️ Edycja bazy"):
                    edited_hist = st.data_editor(hist_data, num_rows="dynamic", use_container_width=True)
                    if st.button("Zapisz zmiany"):
                        save_data(HIST_FILE, edited_hist)
                        st.rerun()

        with t4:
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                with st.form("form_dyspozycja", clear_on_submit=True):
                    st.markdown("#### Nowe zadanie")
                    tresc_dysp = st.text_area("Treść")
                    if st.form_submit_button("Wyślij", type="primary"):
                        if tresc_dysp:
                            dyspo_data.insert(0, {"id": str(uuid.uuid4()), "tresc": tresc_dysp, "data_dodania": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            save_data(DYSPOZYCJE_FILE, dyspo_data)
                            st.rerun()
            with col_d2:
                st.markdown("#### Aktywne zadania")
                for d in dyspo_data:
                    with st.container(border=True):
                        st.markdown(f"**Wysłano:** {d.get('data_dodania')}<br>{d.get('tresc')}", unsafe_allow_html=True)
                        if st.button("Usuń", key=f"del_dysp_{d['id']}"):
                            dyspo_data = [x for x in dyspo_data if str(x.get('id')) != str(d['id'])]
                            save_data(DYSPOZYCJE_FILE, dyspo_data)
                            st.rerun()
                                
        with t5:
            st.markdown("#### Zwroty (RMA)")
            nowe_zwroty = [z for z in zwroty_data if str(z.get('status')) == 'Nowy']
            for z in nowe_zwroty:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**ZAMÓWIENIE NR: {z.get('nr')}**")
                        st.write(f"Zgłoszono: {z.get('data')} | Stan: {z.get('stan')}")
                    with col2:
                        if st.button("Rozpatrzono", key=f"zwr_{z['id']}", use_container_width=True, type="primary"):
                            for item in zwroty_data:
                                if str(item['id']) == str(z['id']):
                                    item['status'] = 'Rozpatrzony'
                                    item['data_rozpatrzenia'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            save_data(ZWROTY_FILE, zwroty_data)
                            st.rerun()

    # ==========================================
    #           TERMINAL PRACOWNIKA (KDS)
    # ==========================================
    elif st.session_state.rola == 'pracownik':
        zam_pracownik = load_data(ZAM_FILE)
        dyspo_pracownik = load_data(DYSPOZYCJE_FILE)
        zwroty_pracownik = load_data(ZWROTY_FILE)
        
        # Audio Alert
        if 'znane_zam' not in st.session_state: st.session_state.znane_zam = {str(z.get('id')) for z in zam_pracownik}
        if 'znane_dysp' not in st.session_state: st.session_state.znane_dysp = {str(d.get('id')) for d in dyspo_pracownik}
        aktualne_zam_ids = {str(z.get('id')) for z in zam_pracownik}
        aktualne_dysp_ids = {str(d.get('id')) for d in dyspo_pracownik}
        if (aktualne_zam_ids - st.session_state.znane_zam) or (aktualne_dysp_ids - st.session_state.znane_dysp):
            st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
            st.toast("🔔 Nowe zadanie!", icon="🔔")
        st.session_state.znane_zam, st.session_state.znane_dysp = aktualne_zam_ids, aktualne_dysp_ids

        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież"): st.rerun()
        if c3.button("Wyloguj"): st.session_state.rola = None; st.rerun()

        tab_kds, tab_dyspo, tab_zwroty, tab_hist = st.tabs(["📦 ZLECENIA", "📌 ZADANIA", "↩️ ZWROT", "🕒 OSTATNIE"])
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")

        with tab_kds:
            if not zam_pracownik:
                st.markdown("<div style='text-align: center; padding: 100px 0;'><h1 style='color: #94a3b8;'>Brak zleceń</h1></div>", unsafe_allow_html=True)
            else:
                cols = st.columns(3)
                for i, z in enumerate(zam_pracownik):
                    with cols[i % 3]:
                        with st.container(border=True):
                            termin_zlecenia = str(z.get('termin', '9999-12-31'))
                            if termin_zlecenia < dzisiaj_str: badge_html = f"<div style='background-color: #fee2e2; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⚠️ ZALEGŁE</div>"
                            elif termin_zlecenia == dzisiaj_str: badge_html = f"<div style='background-color: #fef3c7; color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⏱️ DZISIAJ</div>"
                            else: badge_html = f"<div style='background-color: #f1f5f9; color: #64748b; padding: 4px 10px; border-radius: 6px; font-weight: 700; display: inline-block; margin-bottom: 10px;'>📅 {termin_zlecenia}</div>"

                            st.markdown(f"""<div style='text-align:center;'>{badge_html}<div style='color: #64748b; font-size: 14px;'>Zlecenie Nr</div><div style='font-size: 45px; font-weight: 900;'>{z.get('nr')}</div><hr><div style='font-size: 20px; font-weight: 600; margin-bottom: 20px;'>{z.get('co')}</div></div>""", unsafe_allow_html=True)
                            
                            pdf_data = z.get('pdf_base64', "")
                            if pdf_data and len(str(pdf_data)) > 10:
                                try:
                                    pdf_bytes = base64.b64decode(pdf_data)
                                    st.download_button(label="🖨️ OTWÓRZ ETYKIETĘ", data=pdf_bytes, file_name=f"Etykieta_{z.get('nr')}.pdf", mime="application/pdf", use_container_width=True)
                                except Exception:
                                    st.error("Błąd PDF")
                            
                            if st.button("ZAKOŃCZ", key=f"kds_{z['id']}", use_container_width=True, type="primary"):
                                move_to_history(z['id'])
                                st.rerun()

        with tab_dyspo:
            for d in dyspo_pracownik:
                with st.container(border=True):
                    st.markdown(f"<div style='background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px;'><b>📌 DYSPOZYCJA:</b><br>{d.get('tresc')}</div>", unsafe_allow_html=True)
                    if st.button("ZROBIONE", key=f"dysp_{d['id']}", use_container_width=True):
                        move_dyspozycja_to_history(d['id'])
                        st.rerun()

        with tab_zwroty:
            with st.form("form_zwrot", clear_on_submit=True):
                nr_zwr = st.text_input("Numer zamówienia")
                stan_zwr = st.selectbox("Stan", ["Pełnowartościowy", "Uszkodzony"])
                notatki_zwr = st.text_area("Notatki")
                if st.form_submit_button("ZAREJESTRUJ ZWROT", type="primary"):
                    if nr_zwr:
                        zwroty_pracownik.insert(0, {"id": str(uuid.uuid4()), "nr": nr_zwr, "stan": stan_zwr, "status": "Nowy", "data": datetime.now().strftime("%Y-%m-%d %H:%M"), "notatki": notatki_zwr})
                        save_data(ZWROTY_FILE, zwroty_pracownik)
                        st.success("Zwrot zapisany!")
                    else: st.error("Podaj numer.")

        with tab_hist:
            hist = load_data(HIST_FILE)[:10] 
            for h in hist:
                with st.expander(f"✔️ {h.get('nr')} | {h.get('data_pakowania')}"):
                    if st.button("Cofnij", key=f"w_undo_{h['id']}", use_container_width=True):
                        restore_from_history(h['id']); st.rerun()
