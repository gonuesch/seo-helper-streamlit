# Dockerfile (Finale Version)
# Verwende ein offizielles Python-Basis-Image
FROM python:3.9-slim

# Setze das Arbeitsverzeichnis in dem Container
WORKDIR /app

# Kopiere zuerst die Konfigurations- und Anforderungsdateien
COPY requirements.txt ./
# Die folgende Zeile ist optional, da "COPY . ." sie auch erfasst, aber schadet nicht.
COPY .streamlit/config.toml ./.streamlit/config.toml

# Installiere die Pakete
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den gesamten restlichen Anwendungs-Code
COPY . .

# Der Befehl, um die App zu starten.
# Wir verwenden die Shell-Form und geben den Port explizit an, um alle Zweifel auszuräumen.
CMD streamlit run seo_app.py --server.port=$PORT --server.address=0.0.0.0