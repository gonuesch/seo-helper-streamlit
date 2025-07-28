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

# Gib den Port an, den Cloud Run erwartet.
EXPOSE 8080

# HIER IST DIE KORREKTUR:
# Wir entfernen die ["..."]-Notation, um die Shell-Form zu verwenden.
# Nur so wird die $PORT-Variable von der Shell korrekt ersetzt.
CMD streamlit run seo_app.py --server.port=$PORT --server.address=0.0.0.0