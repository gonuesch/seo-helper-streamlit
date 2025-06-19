# seo_app.py (ULTIMATIVE TESTVERSION)

import streamlit as st
import streamlit_authenticator as stauth
# Direkter Import der untergeordneten Klassen
from streamlit_authenticator.controllers.authentication_controller import AuthenticationController
from streamlit_authenticator.controllers.cookie_controller import CookieController

st.set_page_config(page_title="Auth Test", layout="wide")
st.header("Ultimativer Authentifizierungs-Test")

# Lade die Anmeldedaten
google_client_id = st.secrets.get("GOOGLE_CLIENT_ID")
google_client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET")
cookie_signature_key = st.secrets.get("COOKIE_SIGNATURE_KEY")

if not all([google_client_id, google_client_secret, cookie_signature_key]):
    st.error("🚨 App ist nicht korrekt konfiguriert (OAuth oder Cookie-Schlüssel fehlt).")
    st.stop()

# Erstelle die Konfigurations-Teile einzeln
credentials = {'usernames': {}}
cookie_config = {
    'name': 'test_cookie_final_v2',
    'key': cookie_signature_key,
    'expiry_days': 30
}
providers_config = {
    'google': {
        'client_id': google_client_id,
        'client_secret': google_client_secret,
        'redirect_uri': "https://seo-apper-develop-qeajnwycwxewxdwq4dtgwn.streamlit.app/",
    }
}

st.info("Versuche, die Controller direkt zu initialisieren...")

try:
    # Wir umgehen die Haupt-Authenticate-Klasse und initialisieren die Controller manuell
    auth_controller = AuthenticationController(credentials)
    cookie_controller = CookieController(cookie_config['name'], cookie_config['key'], cookie_config['expiry_days'])
    
    # Erstelle ein "leeres" Authenticator-Objekt und fülle es manuell
    # Dies ist nicht der vorgesehene Weg, aber ein Versuch, den Bug zu umgehen
    authenticator = stauth.Authenticate({}, "", "") # Leere Initialisierung
    authenticator.authentication_controller = auth_controller
    authenticator.cookie_controller = cookie_controller
    # Manuelles Hinzufügen der Provider-Logik (vereinfacht)
    # Hinweis: Dies ist nur zum Testen der Initialisierung, der Login wird so nicht voll funktionieren.

    st.success("Controller erfolgreich initialisiert. Der Fehler liegt tiefer.")

except Exception as e:
    st.error("FEHLER BEI DER DIREKTEN INITIALISIERUNG:")
    st.exception(e)