import streamlit as st
import json
import os
import uuid
import base64
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io
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

# --- 3. POŁĄCZENIE GOOGLE (SHEETS + DRIVE) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_drive_service():
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build('drive', 'v3', credentials=creds)

try:
    DRIVE_SERVICE = get_drive_service()
except Exception as e:
    st.error(f"Nie udało się połączyć z Google Drive. Sprawdź sekrety: {e}")

FOLDER_ID = st.secrets.get("drive_folder_id", "")

ZAM_FILE = "Zamowienia"
HIST_FILE = "Historia"
DYSPOZYCJE_FILE = "Dyspozycje"
ZWROTY_FILE = "Zwroty"

HASLO_SZEFA = "admin123"
HASLO_PRACOWNIKA = "paka123"

# Definicja nagłówków - zaktualizowana o pdf_drive_id
SHEET_HEADERS = {
    "Zamowienia": ["id", "nr", "co", "termin", "pdf_drive_id"],
    "Historia": ["id", "nr", "co", "termin", "pdf_drive_id", "data_pakowania"],
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
        # Tworzymy pusty DataFrame z odpowiednimi nagłówkami, 
        # aby uniknąć błędu IncorrectCellLabel przy zapisie pustej listy
        df = pd.DataFrame(columns=SHEET_HEADERS.get(sheet_name, []))
    else:
        df = pd.DataFrame(data)
        
    try:
        conn.update(worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"Błąd zapisu do Arkusza Google ({sheet_name}): {e}")

def upload_pdf_to_drive(file_content, filename):
    if not FOLDER_ID: 
        st.error("Brak skonfigurowanego folderu Google Drive (drive_folder_id)")
        return ""
    try:
        file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf')
        file = DRIVE_SERVICE.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Błąd wysyłania pliku na Drive: {e}")
        return ""

def download_pdf_from_drive(file_id):
    try:
        request = DRIVE_SERVICE.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        st.error(f"Błąd pobierania z Drive: {e}")
        return None

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
        
        c1, c2, c3 = st.columns([6, 2, 2])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>PANEL SZEFA</h2>", unsafe_allow_html=True)
        c2.markdown("<div style='text-align: right; margin-top: 5px;'><b>Użytkownik:</b> Administrator 👨‍💼</div>", unsafe_allow_html=True)
        if c3.button("Wyloguj się", use_container_width=True):
            st.session_state.rola = None
            st.rerun()
        st.divider()

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
                    plik_etykiety = st.file_uploader("Załącz list przewozowy / etykietę (PDF)", type=["pdf"])
                    
                    if st.form_submit_button("PRZEKAŻ NA MAGAZYN", type="primary"):
                        if nr and co:
                            drive_id = ""
                            if plik_etykiety is not None:
                                drive_id = upload_pdf_to_drive(plik_etykiety.read(), f"Etykieta_{nr}.pdf")

                            zam_data.append({
                                "id": str(uuid.uuid4()), 
                                "nr": nr, 
                                "co": co, 
                                "termin": termin.strftime("%Y-%m-%d"),
                                "pdf_drive_id": drive_id
                            })
                            zam_data.sort(key=lambda x: str(x.get('termin', '9999-12-31')))
                            save_data(ZAM_FILE, zam_data)
                            st.toast(f"Pomyślnie dodano: {nr}", icon="✅")
                            st.rerun() 
                        else:
                            st.toast("Wypełnij wymagane pola formularza.", icon="❗️")

        with t2:
            st.markdown("#### Zlecenia w trakcie realizacji przez pakownię")
            if not zam_data:
                st.info("Obecnie pracownicy nie mają żadnych aktywnych zleceń.")
            else:
                for z in zam_data:
                    with st.expander(f"ZAM: {z['nr']}  |  Wymagany termin: {z.get('termin', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        info_text = f"**Co spakować:**<br>{z['co']}"
                        if z.get('pdf_drive_id'): 
                            info_text += "<br><span style='color:#1e3a8a;'>📄 Dołączono etykietę PDF</span>"
                        col_info.markdown(info_text, unsafe_allow_html=True)
                        
                        if col_action.button("Wycofaj (Usuń)", key=f"boss_cancel_{z['id']}", use_container_width=True):
                            zam_data = [x for x in zam_data if str(x.get('id')) != str(z['id'])]
                            save_data(ZAM_FILE, zam_data)
                            st.rerun()

        with t3:
            st.markdown("#### Dziennik operacji (Zamówienia)")
            if not hist_data:
                st.info("Brak wpisów w dzienniku.")
            else:
                for h in hist_data:
                    with st.expander(f"✔️ ZAM: {h.get('nr')}  |  Wykonano: {h.get('data_pakowania', 'Brak')}"):
                        col_info, col_action = st.columns([4, 1])
                        col_info.markdown(f"**Szczegóły:**<br>{h.get('co')}", unsafe_allow_html=True)
                        if col_action.button("Przywróć na produkcję", key=f"boss_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚙️ Zaawansowana administracja rekordami"):
                    edited_hist = st.data_editor(hist_data, num_rows="dynamic", use_container_width=True)
                    if st.button("Zapisz zmiany w bazie zamówień"):
                        save_data(HIST_FILE, edited_hist)
                        st.toast("Zaktualizowano.", icon="💾")

        with t4:
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                with st.form("form_dyspozycja", clear_on_submit=True):
                    st.markdown("#### Dodaj nowe zadanie poboczne")
                    tresc_dysp = st.text_area("Treść zadania")
                    if st.form_submit_button("Wyślij Dyspozycję", type="primary"):
                        if tresc_dysp:
                            dyspo_data.insert(0, {
                                "id": str(uuid.uuid4()), "tresc": tresc_dysp,
                                "data_dodania": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            save_data(DYSPOZYCJE_FILE, dyspo_data)
                            st.rerun()
            with col_d2:
                st.markdown("#### Aktywne zadania")
                if not dyspo_data:
                    st.info("Brak aktywnych zadań.")
                else:
                    for d in dyspo_data:
                        with st.container(border=True):
                            st.markdown(f"**Wysłano:** {d.get('data_dodania')}<br>{d.get('tresc')}", unsafe_allow_html=True)
                            if st.button("Usuń", key=f"del_dysp_{d['id']}"):
                                dyspo_data = [x for x in dyspo_data if str(x.get('id')) != str(d['id'])]
                                save_data(DYSPOZYCJE_FILE, dyspo_data)
                                st.rerun()
                                
        with t5:
            st.markdown("#### Obsługa Zwrotów i Reklamacji (RMA)")
            nowe_zwroty = [z for z in zwroty_data if str(z.get('status')) == 'Nowy']
            stare_zwroty = [z for z in zwroty_data if str(z.get('status')) == 'Rozpatrzony']
            
            st.markdown("##### 🔴 Oczekujące na Twoją decyzję")
            if not nowe_zwroty:
                st.success("Wszystkie zwroty zostały rozpatrzone.")
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
                                save_data(ZWROTY_FILE, zwroty_data)
                                st.rerun()
            st.divider()
            with st.expander("📁 Archiwum rozwiązanych zwrotów"):
                for z in stare_zwroty:
                    st.markdown(f"**{z.get('nr')}** - Stan: {z.get('stan')}")

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

        nowe_zam = aktualne_zam_ids - st.session_state.znane_zam
        nowe_dysp = aktualne_dysp_ids - st.session_state.znane_dysp

        st.session_state.znane_zam = aktualne_zam_ids
        st.session_state.znane_dysp = aktualne_dysp_ids

        if nowe_zam or nowe_dysp:
            st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
            st.toast("🔔 Nowe zadanie na terminalu!", icon="🔔")

        c1, c2, c3 = st.columns([6, 1, 1])
        c1.markdown("<h2 style='color: #1e3a8a; margin-top: -15px; font-weight: 800;'>TERMINAL KOMPLETACJI</h2>", unsafe_allow_html=True)
        if c2.button("🔄 Odśwież", use_container_width=True): st.rerun()
        if c3.button("Wyloguj", use_container_width=True): 
            st.session_state.rola = None
            st.rerun()

        tab_kds, tab_dyspo, tab_zwroty, tab_hist = st.tabs(["📦 AKTYWNE ZLECENIA", "📌 TABLICA ZADAŃ", "↩️ PRZYJMIJ ZWROT", "🕒 OSTATNIE OPERACJE"])
        dzisiaj_str = datetime.now().strftime("%Y-%m-%d")

        with tab_kds:
            if not zam_pracownik:
                st.markdown("<div style='text-align: center; padding: 100px 0;'><h1 style='color: #94a3b8;'>Brak aktywnych zleceń</h1></div>", unsafe_allow_html=True)
            else:
                cols = st.columns(3)
                for i, z in enumerate(zam_pracownik):
                    with cols[i % 3]:
                        with st.container(border=True):
                            termin_zlecenia = str(z.get('termin', '9999-12-31'))
                            if termin_zlecenia < dzisiaj_str: badge_html = f"<div style='background-color: #fee2e2; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⚠️ ZALEGŁE: {termin_zlecenia}</div>"
                            elif termin_zlecenia == dzisiaj_str: badge_html = f"<div style='background-color: #fef3c7; color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-weight: 800; display: inline-block; margin-bottom: 10px;'>⏱️ NA DZISIAJ</div>"
                            else: badge_html = f"<div style='background-color: #f1f5f9; color: #64748b; padding: 4px 10px; border-radius: 6px; font-weight: 700; display: inline-block; margin-bottom: 10px;'>📅 Termin: {termin_zlecenia}</div>"

                            st.markdown(f"""
                            <div style='text-align:center;'>
                                {badge_html}
                                <div style='color: #64748b; font-size: 14px; font-weight: bold;'>Zlecenie Nr</div>
                                <div style='font-size: 50px; font-weight: 900; line-height: 1.1; margin-bottom: 10px;'>{z.get('nr')}</div>
                                <hr style='margin: 15px 0; border-top: 1px dashed #cbd5e1;'>
                                <div style='font-size: 20px; font-weight: 600; margin-bottom: 20px;'>{z.get('co')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Pobieranie PDF
                            drive_id = z.get('pdf_drive_id', "")
                            if drive_id:
                                pdf_bytes = download_pdf_from_drive(drive_id)
                                if pdf_bytes:
                                    st.download_button(
                                        label="🖨️ OTWÓRZ ETYKIETĘ",
                                        data=pdf_bytes,
                                        file_name=f"Etykieta_{z.get('nr')}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                                else:
                                    st.error("Etykieta niedostępna")
                            
                            st.write("") 
                            if st.button("ZAKOŃCZ ZLECENIE", key=f"kds_{z['id']}", use_container_width=True, type="primary"):
                                move_to_history(z['id'])
                                st.rerun()

        with tab_dyspo:
            if not dyspo_pracownik:
                st.markdown("<div style='text-align: center; padding: 80px 0;'><h1 style='color: #94a3b8;'>Brak dodatkowych zadań</h1></div>", unsafe_allow_html=True)
            else:
                d_cols = st.columns(3)
                for i, d in enumerate(dyspo_pracownik):
                    with d_cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style='background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 15px;'>
                                <div style='color: #b45309; font-size: 12px; font-weight: bold;'>📌 DYSPOZYCJA Z: {d.get('data_dodania', '')}</div>
                                <div style='font-size: 18px; font-weight: 600;'>{d.get('tresc')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("POTWIERDŹ WYKONANIE", key=f"dysp_{d['id']}", use_container_width=True):
                                move_dyspozycja_to_history(d['id'])
                                st.rerun()

        with tab_zwroty:
            st.markdown("### Wprowadź paczkę zwrotną do systemu")
            col1, col2 = st.columns([1, 1])
            with col1:
                with st.form("formularz_zwrotu", clear_on_submit=True):
                    nr_zwr = st.text_input("Numer zwracanego zamówienia")
                    stan_zwr = st.selectbox("Stan towaru", ["Pełnowartościowy", "Uszkodzony"])
                    powod_zwr = st.selectbox("Powód zwrotu", ["Brak", "Odstąpienie 14 dni", "Reklamacja"])
                    notatki_zwr = st.text_area("Uwagi dla szefa")
                    if st.form_submit_button("ZAREJESTRUJ ZWROT", type="primary"):
                        if nr_zwr:
                            zwroty_pracownik.insert(0, {
                                "id": str(uuid.uuid4()), "nr": nr_zwr, "stan": stan_zwr,
                                "powod": powod_zwr, "notatki": notatki_zwr, "status": "Nowy",
                                "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            save_data(ZWROTY_FILE, zwroty_pracownik)
                            st.toast("Zwrot zarejestrowany!", icon="✅")
                            st.rerun()
                        else: st.error("Podaj chociaż numer zamówienia.")

        with tab_hist:
            hist = load_data(HIST_FILE)[:15] 
            if not hist:
                st.info("Brak historii z dzisiejszej zmiany.")
            else:
                for h in hist:
                    with st.expander(f"✔️ ZAM: {h.get('nr')}  |  Wykonano: {h.get('data_pakowania', '')}"):
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"**Zawartość:** {h.get('co')}")
                        if col2.button("Cofnij zlecenie na ekran", key=f"w_undo_{h['id']}", use_container_width=True):
                            restore_from_history(h['id'])
                            st.rerun()
