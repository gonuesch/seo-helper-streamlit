# Dockerfile (Finale, korrigierte Version)
FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Wir verwenden wieder die Shell-Form und übergeben den Port explizit,
# da dies in der Cloud Run-Umgebung erforderlich ist.
CMD streamlit run seo_app.py --server.port=$PORT --server.address=0.0.0.0