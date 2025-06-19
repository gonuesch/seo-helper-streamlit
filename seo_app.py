import streamlit as st

st.set_page_config(page_title="Auth Debug", layout="wide")

try:
    st.write("Attempting to read secrets...")
    client_id = st.secrets.connections.google_oauth.client_id
    st.success("Successfully read client_id.")
    client_secret = st.secrets.connections.google_oauth.client_secret
    st.success("Successfully read client_secret.")
    redirect_uri = st.secrets.connections.google_oauth.redirect_uri
    st.success("Successfully read redirect_uri.")
except Exception as e:
    st.error(f"Failed to read secrets: {e}")

st.info("Now attempting to display the login button...")

# Your existing login button code
if not st.user:
    st.button("Mit Google einloggen", on_click=st.login, args=("google",))
else:
    st.write(f"Welcome, {st.user.email}")
    st.button("Logout", on_click=st.logout)