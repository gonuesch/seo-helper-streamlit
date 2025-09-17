# Dockerfile (Finale, korrigierte Version)
FROM python:3.11-slim
WORKDIR /app

# Erst die Anforderungen kopieren, um das Caching von Docker-Layern zu optimieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip show google-cloud-texttospeech

# Dann den Rest des App-Codes kopieren
COPY . .

# Wir verwenden wieder die Shell-Form und übergeben den Port explizit,
# da dies in der Cloud Run-Umgebung erforderlich ist.
CMD streamlit run seo_app.py --server.port=$PORT --server.address=0.0.0.0