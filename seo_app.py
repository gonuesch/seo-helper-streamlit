# seo_app.py (MINIMALE TESTVERSION)

import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(page_title="Auth Test", layout="wide")

st.header("Minimaler Authentifizierungs-Test")

# Lade die Anmeldedaten
google_client_id = st.secrets.get("GOOGLE_CLIENT_ID")
google_client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET")
cookie_signature_key = st.secrets.get("COOKIE_SIGNATURE_KEY")

# Prüfe, ob die Anmeldedaten konfiguriert sind
if not all([google_client_id, google_client_secret, cookie_signature_key]):
    st.error("🚨 App ist nicht korrekt konfiguriert (OAuth oder Cookie-Schlüssel fehlt).")
    st.stop()

# Erstelle das Konfigurations-Dictionary
config = {
    'credentials': {'usernames': {}},
    'cookie': {
        'name': 'test_cookie_final', # Neuer Name, um alte Cookies zu umgehen
        'key': cookie_signature_key,
        'expiry_days': 30,
    },
    'preauthorized': { # Hinzugefügt für bessere Struktur
        'emails': []
    },
    'providers': {
        'google': {
            'client_id': google_client_id,
            'client_secret': google_client_secret,
            'redirect_uri': "https://seo-apper-develop-qeajnwycwxewxdwq4dtgwn.streamlit.app/",
        },
    },
}

st.info("Versuche, den Authenticator zu initialisieren...")

try:
    authenticator = stauth.Authenticate(config)
    st.success("Authenticator erfolgreich initialisiert.")

    authenticator.login()

    if st.session_state.get("authentication_status"):
        st.success(f"Willkommen, {st.session_state.get('name')}!")
        authenticator.logout('Logout', 'main')
    elif st.session_state.get("authentication_status") is False:
        st.error('Login fehlgeschlagen.')
    elif st.session_state.get("authentication_status") is None:
        st.warning('Bitte einloggen.')

except Exception as e:
    st.error("FEHLER BEI DER INITIALISIERUNG:")
    st.exception(e)