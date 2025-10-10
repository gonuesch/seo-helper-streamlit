#!/usr/bin/env python3
"""
Script zum Herunterladen der übersetzten Datei aus Google Cloud Storage.
"""
import os
from google.cloud import firestore, storage

# Konfiguration
PROJECT_ID = "avid-infinity-458913-p3"
FIRESTORE_DB_ID = "hbu-toolbox-firestone"
BUCKET_NAME = "manuskripte-upload-avid-infinity"
JOB_ID = "2589143d-32dc-4b15-ace8-4c0206468d27"  # Aus den Logs

def download_translated_file():
    """Lädt die übersetzte Datei herunter."""
    try:
        # Firestore Client
        firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
        
        # Job-Dokument aus Firestore laden
        job_ref = firestore_client.collection("translation_jobs").document(JOB_ID)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            print(f"❌ Job {JOB_ID} nicht in Firestore gefunden")
            return False
        
        job_data = job_doc.to_dict()
        print(f"📋 Job-Status: {job_data.get('status', 'unknown')}")
        print(f"📋 Datei: {job_data.get('file_name', 'unknown')}")
        
        # GCS-Pfad der übersetzten Datei
        final_gcs_path = job_data.get("final_gcs_path")
        if not final_gcs_path:
            print(f"❌ Kein final_gcs_path für Job {JOB_ID} gefunden")
            print(f"📋 Verfügbare Felder: {list(job_data.keys())}")
            return False
        
        print(f"📁 Übersetzte Datei: {final_gcs_path}")
        
        # GCS Client
        storage_client = storage.Client(project=PROJECT_ID)
        
        # Blob-Name extrahieren
        if final_gcs_path.startswith(f"gs://{BUCKET_NAME}/"):
            blob_name = final_gcs_path.replace(f"gs://{BUCKET_NAME}/", "")
        else:
            print(f"❌ Ungültiger GCS-Pfad: {final_gcs_path}")
            return False
        
        # Datei herunterladen
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Lokaler Dateiname
        local_filename = f"translated_{JOB_ID}.docx"
        
        print(f"⬇️ Lade Datei herunter...")
        blob.download_to_filename(local_filename)
        
        print(f"✅ Datei erfolgreich heruntergeladen: {local_filename}")
        print(f"📊 Dateigröße: {os.path.getsize(local_filename)} Bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Herunterladen: {e}")
        return False

if __name__ == "__main__":
    print(f"📥 Lade übersetzte Datei für Job: {JOB_ID}")
    success = download_translated_file()
    if success:
        print(f"🎯 Datei erfolgreich heruntergeladen!")
    else:
        print(f"💥 Fehler beim Herunterladen der Datei")
