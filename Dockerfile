# Dockerfile (Optimierte Version)
# Verwende ein offizielles Python-Basis-Image
FROM python:3.9-slim

# Setze das Arbeitsverzeichnis in dem Container
WORKDIR /app

# Kopiere zuerst die Konfigurations- und Anforderungsdateien
COPY requirements.txt ./
COPY .streamlit/config.toml ./.streamlit/config.toml

# Installiere die Pakete
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den gesamten restlichen Anwendungs-Code
COPY . .

# Der Befehl, um die App zu starten.
# Streamlit liest die config.toml und erkennt $PORT automatisch.
CMD ["streamlit", "run", "seo_app.py"]