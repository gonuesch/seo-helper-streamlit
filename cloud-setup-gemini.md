# Google Cloud Setup - Mit Gemini 2.5 Flash (Kein OpenAI API Key erforderlich)

## 🚀 Google Cloud Setup - Commands für avid-infinity-458913-p3

### **1. APIs aktivieren**
```bash
# Erforderliche APIs aktivieren
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable eventarc.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable storage.googleapis.com
```

### **2. Service Account erstellen**
```bash
# Service Account für Translation Service
gcloud iam service-accounts create translation-service-sa \
  --display-name="Translation Service Account" \
  --description="Service account for Cloud Run translation service" \
  --project avid-infinity-458913-p3

# Erforderliche Berechtigungen zuweisen
gcloud projects add-iam-policy-binding avid-infinity-458913-p3 \
  --member="serviceAccount:translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding avid-infinity-458913-p3 \
  --member="serviceAccount:translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding avid-infinity-458913-p3 \
  --member="serviceAccount:translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding avid-infinity-458913-p3 \
  --member="serviceAccount:translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

### **3. Container Image bauen und deployen**
```bash
# Container Image bauen
gcloud builds submit --tag gcr.io/avid-infinity-458913-p3/translation-service \
  --project avid-infinity-458913-p3

# Cloud Run Service deployen
gcloud run deploy translation-service \
  --image gcr.io/avid-infinity-458913-p3/translation-service \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 1 \
  --set-env-vars GCP_PROJECT=avid-infinity-458913-p3 \
  --service-account translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com \
  --project avid-infinity-458913-p3
```

### **4. Eventarc Trigger einrichten**
```bash
# Eventarc Trigger für Cloud Storage Events
gcloud eventarc triggers create translation-trigger \
  --location europe-west1 \
  --destination-run-service translation-service \
  --destination-run-region europe-west1 \
  --event-filters type=google.cloud.storage.object.v1.finalized \
  --event-filters bucket=manuskripte-upload-avid-infinity \
  --service-account translation-service-sa@avid-infinity-458913-p3.iam.gserviceaccount.com \
  --project avid-infinity-458913-p3
```

### **5. Firestore Database konfigurieren**
```bash
# Firestore Database erstellen (falls noch nicht vorhanden)
gcloud firestore databases create \
  --database-id hbu-toolbox-firestone \
  --location europe-west1 \
  --project avid-infinity-458913-p3
```

### **6. Cloud Storage Bucket konfigurieren**
```bash
# Bucket für übersetzte Dokumente (falls noch nicht vorhanden)
gsutil mb gs://manuskripte-upload-avid-infinity \
  --project avid-infinity-458913-p3
```

## 🔧 **Automatisierte Migration (Empfohlen)**

```bash
# Migration automatisch durchführen
python migrate-to-cloud-run.py avid-infinity-458913-p3 europe-west1
```

## 🧪 **Deployment testen**

```bash
# Service URL abrufen
SERVICE_URL=$(gcloud run services describe translation-service \
  --region europe-west1 \
  --format="value(status.url)" \
  --project avid-infinity-458913-p3)

# Deployment testen
python test-deployment.py $SERVICE_URL
```

## 📊 **Monitoring einrichten**

```bash
# Logs überwachen
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=translation-service" \
  --limit 50 \
  --project avid-infinity-458913-p3

# Service Status prüfen
gcloud run services describe translation-service \
  --region europe-west1 \
  --project avid-infinity-458913-p3
```

## ✅ **Vorteile der Gemini 2.5 Flash Integration**

### **Kein OpenAI API Key erforderlich**
- ✅ Alles läuft innerhalb der Google Cloud
- ✅ Keine externen API-Abhängigkeiten
- ✅ Bessere Integration mit Google Cloud Services
- ✅ Konsistente Authentifizierung über Service Account

### **Verbesserte Performance**
- ✅ **Gemini 2.5 Flash** für Übersetzungen (schneller und effizienter)
- ✅ **textembedding-gecko@003** für Semantic Chunking (Google's Embedding Model)
- ✅ Optimierte Integration zwischen Translation und Embedding Models
- ✅ Reduzierte Latenz durch interne Google Cloud Kommunikation

### **Kosteneffizienz**
- ✅ Keine separaten OpenAI API Kosten
- ✅ Google Cloud Pricing für alle Services
- ✅ Bessere Kostenkontrolle und Monitoring
- ✅ Einheitliche Abrechnung

## 🎯 **Nach dem Setup**

Der Service wird dann automatisch:
- ✅ Bei neuen Dateien im `manuskripte-upload-avid-infinity` Bucket ausgelöst
- ✅ Dokumente in 50-Seiten-Chunks verarbeiten
- ✅ **Gemini 2.5 Flash** für Übersetzungen verwenden
- ✅ **Google's Embedding Model** für Semantic Chunking verwenden
- ✅ Übersetzte Dokumente zurück in Cloud Storage speichern
- ✅ Fortschritt in Firestore verfolgen

**Der Service ist dann bereit für die Produktion mit vollständiger Google Cloud Integration!** 🚀
