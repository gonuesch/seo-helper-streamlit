# Cloud Run Translation Service Deployment Guide

## Overview
This guide covers deploying the refactored translation service to Google Cloud Run, replacing the previous Cloud Function implementation.

## Prerequisites
- Google Cloud Project with billing enabled
- Cloud Run API enabled
- Cloud Build API enabled
- Container Registry or Artifact Registry access
- Service account with appropriate permissions

## Environment Variables Required

Set these environment variables in your Cloud Run service:

```bash
# Required
GCP_PROJECT=your-project-id
OPENAI_API_KEY=your-openai-api-key  # For semantic chunking embeddings

# Optional (with defaults)
FIRESTORE_DB_ID=hbu-toolbox-firestone
LOCATION=europe-west1
BUCKET_NAME=manuskripte-upload-avid-infinity
MAX_COST_PER_JOB_USD=10.0
MAX_RUNTIME_MINUTES=120
```

## Cloud Run Configuration

### Service Configuration
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: translation-service
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/memory: "4Gi"
        run.googleapis.com/cpu: "2"
        run.googleapis.com/timeout: "3600s"
        run.googleapis.com/max-scale: "10"
        run.googleapis.com/min-scale: "0"
    spec:
      containerConcurrency: 1
      timeoutSeconds: 3600
      containers:
      - image: gcr.io/PROJECT_ID/translation-service:latest
        ports:
        - containerPort: 8080
        env:
        - name: GCP_PROJECT
          value: "your-project-id"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-api-key
              key: key
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
          requests:
            cpu: "1"
            memory: "2Gi"
```

### Deployment Commands

1. **Build and Deploy using Cloud Build:**
```bash
# Build the container
gcloud builds submit --tag gcr.io/PROJECT_ID/translation-service

# Deploy to Cloud Run
gcloud run deploy translation-service \
  --image gcr.io/PROJECT_ID/translation-service \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 1 \
  --set-env-vars GCP_PROJECT=your-project-id
```

2. **Set up Eventarc Trigger:**
```bash
# Create Eventarc trigger for Cloud Storage events
gcloud eventarc triggers create translation-trigger \
  --location=europe-west1 \
  --destination-run-service=translation-service \
  --destination-run-region=europe-west1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=your-bucket-name"
```

## Key Differences from Cloud Function

### Advantages of Cloud Run Migration:
1. **Longer Timeouts**: Up to 3600 seconds (1 hour) vs 540 seconds for Cloud Functions
2. **More Memory**: Up to 4GB vs 512MB for Cloud Functions
3. **Better Resource Management**: Dedicated CPU and memory allocation
4. **Improved Monitoring**: Better observability and debugging
5. **Cost Efficiency**: Pay only for actual usage with min-instances=0

### Performance Optimizations:
- **Memory-Efficient Processing**: Files processed in batches, not loaded entirely into memory
- **Semantic Chunking**: Intelligent text splitting for better translation quality
- **Page Batching**: Document processing in 50-page chunks
- **Structure Preservation**: Maintains document formatting and paragraph structure

## Monitoring and Logging

### Cloud Logging
The service logs detailed information about:
- Translation progress and chunk processing
- Memory usage and performance metrics
- Error handling and recovery attempts
- Cost tracking and safety limits

### Key Metrics to Monitor:
- Request duration and timeout rates
- Memory usage patterns
- Translation success rates
- Cost per translation job

## Security Considerations

1. **Service Account Permissions:**
   - Cloud Storage Object Viewer
   - Firestore User
   - Vertex AI User
   - Cloud Logging Writer

2. **Network Security:**
   - VPC connector if needed for private resources
   - IAM-based access control
   - Secret management for API keys

3. **Data Protection:**
   - Temporary files are cleaned up after processing
   - No persistent storage of sensitive data
   - Secure handling of API keys

## Troubleshooting

### Common Issues:
1. **Memory Issues**: Increase memory allocation or optimize batch sizes
2. **Timeout Issues**: Increase timeout or optimize processing speed
3. **API Rate Limits**: Implement exponential backoff and retry logic
4. **Cost Overruns**: Monitor and adjust safety limits

### Debug Commands:
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=translation-service"

# Check service status
gcloud run services describe translation-service --region=europe-west1
```

## Migration Checklist

- [ ] Build and deploy container image
- [ ] Configure environment variables
- [ ] Set up Eventarc trigger
- [ ] Test with sample documents
- [ ] Monitor performance and costs
- [ ] Update any dependent services
- [ ] Decommission old Cloud Function (if applicable)

## Cost Optimization

1. **Resource Allocation**: Start with 2GB memory, scale up if needed
2. **Concurrency**: Set to 1 for memory-intensive operations
3. **Scaling**: Use min-instances=0 to avoid idle costs
4. **Timeout**: Set appropriate timeout to avoid unnecessary charges

This deployment provides a robust, scalable solution for document translation with improved memory efficiency and translation quality.
