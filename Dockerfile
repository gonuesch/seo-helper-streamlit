# Dockerfile (Finale, korrigierte Version)
FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Wir verwenden wieder die Shell-Form und übergeben den Port explizit,
# da dies in der Cloud Run-Umgebung erforderlich ist.
CMD streamlit run seo_app.py --server.port=$PORT --server.address=0.0.0.0

import logging
import sys

# Debug-Logging für Streamlit und Authlib
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/streamlit_debug.log')
    ]
)

# Spezifische Logger für Authlib
logging.getLogger('authlib').setLevel(logging.DEBUG)
logging.getLogger('streamlit').setLevel(logging.DEBUG)