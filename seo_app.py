# seo_app.py (NEUE DEBUG-VERSION BASIEREND AUF [auth])

import streamlit as st

st.set_page_config(page_title="Auth Debug v2", layout="wide")
st.header("Auth Debugger (Prüfung der `[auth]`-Secrets)")

# Wir prüfen, ob das übergeordnete 'auth'-Objekt in den Secrets existiert
if "auth" not in st.secrets:
    st.error("FEHLER: Es wurde keine `[auth]`-Sektion in den Secrets gefunden!")
    st.write("Bitte stelle sicher, dass deine Secrets `auth_client_id`, `auth_client_secret` etc. heißen.")
    st.stop()

# Wir prüfen jeden einzelnen Schlüssel innerhalb von st.secrets.auth
st.info("`[auth]`-Sektion gefunden. Prüfe einzelne Schlüssel...")
all_keys_found = True
required_keys = ["client_id", "client_secret", "redirect_uri", "cookie_secret", "server_metadata_url"]

for key in required_keys:
    if key not in st.secrets.auth:
        st.error(f"FEHLER: Der Schlüssel '{key}' fehlt in der `[auth]`-Sektion deiner Secrets!")
        all_keys_found = False
    else:
        st.success(f"Schlüssel '{key}' erfolgreich gefunden.")

if not all_keys_found:
    st.stop()

st.success("Perfekt! Alle notwendigen `auth`-Secrets sind vorhanden und korrekt benannt.")
st.info("Versuche jetzt, den Login-Button anzuzeigen...")

# Finaler Test des Login-Buttons
try:
    if not st.user:
        st.button("Mit Google einloggen", on_click=st.login, args=("google",), key="login_button")
    else:
        st.write(f"Willkommen, {st.user.name}!")
        st.button("Logout", on_click=st.logout, key="logout_button")
except Exception as e:
    st.error("Ein Fehler ist beim Aufruf von st.login() aufgetreten:")
    st.exception(e)