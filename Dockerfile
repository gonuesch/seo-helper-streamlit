# Dockerfile
# Verwende ein offizielles Python-Basis-Image
FROM python:3.9-slim

# Setze das Arbeitsverzeichnis in dem Container
WORKDIR /app

# Kopiere die Abhängigkeits-Datei und installiere die Pakete
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den gesamten restlichen Anwendungs-Code
COPY . .

# Gib den Port an, auf dem Streamlit läuft
EXPOSE 8501

# Der Befehl, um die App zu starten
CMD ["streamlit", "run", "seo_app.py", "--server.port=8501", "--server.address=0.0.0.0"]