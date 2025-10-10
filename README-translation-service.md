# Cloud Run Translation Service

A robust, scalable, and memory-efficient document translation service built for Google Cloud Run. This service has been refactored from a Cloud Function implementation to handle long-running translation tasks with improved memory efficiency and higher translation quality.

## 🚀 Key Features

### **Memory Efficiency**
- **Page-batching processing**: Documents are processed in 50-page chunks to avoid loading entire files into memory
- **Temporary file handling**: Files are downloaded to temporary local storage instead of being loaded into memory
- **Generator-based text extraction**: Memory usage remains constant regardless of document size

### **Enhanced Translation Quality**
- **Semantic chunking**: Uses LangChain's SemanticChunker for intelligent text splitting based on semantic boundaries
- **Multi-part prompts**: Detailed prompts with system instructions, few-shot examples, and style guides
- **Context preservation**: Maintains translation context across chunks for better coherence
- **Structure preservation**: Document formatting and paragraph structure are maintained

### **Scalability & Performance**
- **Cloud Run deployment**: Handles long-running tasks (up to 1 hour timeout vs 9 minutes for Cloud Functions)
- **Resource optimization**: 4GB memory allocation with dedicated CPU resources
- **Intelligent scaling**: Auto-scales from 0 to 10 instances based on demand
- **Cost efficiency**: Pay only for actual usage with min-instances=0

## 📁 Project Structure

```
├── main.py                          # Main Flask application with all translation logic
├── Dockerfile                       # Cloud Run container configuration
├── requirements.txt                 # Python dependencies
├── cloudbuild.yaml                  # Automated deployment pipeline
├── performance-config.yaml          # Optimized Cloud Run configuration
├── cloud-run-deployment.md          # Detailed deployment guide
├── test-deployment.py               # Deployment testing script
└── README-translation-service.md    # This file
```

## 🛠️ Architecture Overview

### **Request Flow**
1. **Eventarc Trigger**: Cloud Storage object creation triggers the service
2. **File Download**: Document downloaded to temporary local storage
3. **Text Extraction**: Page-batching generators extract text in manageable chunks
4. **Semantic Chunking**: LangChain splits text based on semantic boundaries
5. **Translation**: Gemini 1.5 Flash translates each chunk with context
6. **Document Reconstruction**: Translated chunks reassembled into structured DOCX
7. **Upload**: Final document uploaded to Cloud Storage

### **Memory Management**
```
Original (Cloud Function):     New (Cloud Run):
┌─────────────────────┐       ┌─────────────────────┐
│ Load entire file   │  →    │ Download to temp   │
│ into memory        │       │ Process in batches  │
│ (512MB limit)      │       │ (4GB available)     │
└─────────────────────┘       └─────────────────────┘
```

## 🚀 Quick Start

### **Prerequisites**
- Google Cloud Project with billing enabled
- Cloud Run, Cloud Build, and Container Registry APIs enabled
- Service account with appropriate permissions
- OpenAI API key for semantic chunking

### **Deployment**

1. **Set Environment Variables:**
```bash
export GCP_PROJECT=your-project-id
export OPENAI_API_KEY=your-openai-api-key
```

2. **Deploy using Cloud Build:**
```bash
gcloud builds submit --config cloudbuild.yaml
```

3. **Set up Eventarc Trigger:**
```bash
gcloud eventarc triggers create translation-trigger \
  --location=europe-west1 \
  --destination-run-service=translation-service \
  --destination-run-region=europe-west1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=your-bucket-name"
```

4. **Test Deployment:**
```bash
python test-deployment.py https://translation-service-xxx-uc.a.run.app
```

## 📊 Performance Improvements

| Metric | Cloud Function | Cloud Run | Improvement |
|--------|----------------|-----------|-------------|
| **Memory** | 512MB | 4GB | 8x increase |
| **Timeout** | 9 minutes | 60 minutes | 6.7x increase |
| **CPU** | Shared | Dedicated | Better performance |
| **Scaling** | Automatic | 0-10 instances | More control |
| **Cost** | Per invocation | Per usage | More efficient |

## 🔧 Configuration

### **Environment Variables**
```bash
# Required
GCP_PROJECT=your-project-id
OPENAI_API_KEY=your-openai-api-key

# Optional (with defaults)
FIRESTORE_DB_ID=hbu-toolbox-firestone
LOCATION=europe-west1
BUCKET_NAME=manuskripte-upload-avid-infinity
MAX_COST_PER_JOB_USD=10.0
MAX_RUNTIME_MINUTES=120
```

### **Resource Allocation**
- **Memory**: 4GB (configurable)
- **CPU**: 2 vCPUs (configurable)
- **Timeout**: 3600 seconds (1 hour)
- **Concurrency**: 1 (for memory-intensive operations)

## 🧠 Translation Quality Features

### **Semantic Chunking**
- Uses LangChain's SemanticChunker for intelligent text splitting
- Maintains semantic boundaries for better translation context
- Fallback to paragraph-based chunking if semantic chunking fails

### **Enhanced Prompts**
- **System Instruction**: Expert literary translator persona
- **Few-shot Examples**: High-quality German-English translation examples
- **Style Guides**: Genre, tone, and stylistic preferences
- **Key Terms**: Consistent terminology translation
- **Context Awareness**: Previous chunk context for coherence

### **Document Structure Preservation**
- Paragraph structure maintained
- Formatting preserved
- Page breaks respected
- Document metadata retained

## 📈 Monitoring & Logging

### **Cloud Logging Integration**
- Detailed translation progress tracking
- Memory usage and performance metrics
- Error handling and recovery attempts
- Cost tracking and safety limits

### **Key Metrics**
- Request duration and timeout rates
- Memory usage patterns
- Translation success rates
- Cost per translation job

## 🔒 Security

### **Service Account Permissions**
- Cloud Storage Object Viewer
- Firestore User
- Vertex AI User
- Cloud Logging Writer

### **Data Protection**
- Temporary files cleaned up after processing
- No persistent storage of sensitive data
- Secure API key handling
- VPC connector support for private resources

## 🚨 Troubleshooting

### **Common Issues**

1. **Memory Issues**
   - Increase memory allocation in Cloud Run configuration
   - Optimize batch sizes in page-batching functions
   - Monitor memory usage in Cloud Logging

2. **Timeout Issues**
   - Increase timeout in Cloud Run configuration
   - Optimize processing speed
   - Check for infinite loops in processing

3. **API Rate Limits**
   - Implement exponential backoff
   - Add retry logic with jitter
   - Monitor API usage patterns

4. **Cost Overruns**
   - Adjust safety limits in environment variables
   - Monitor cost per job in Firestore
   - Implement cost alerts

### **Debug Commands**
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=translation-service"

# Check service status
gcloud run services describe translation-service --region=europe-west1

# Monitor resource usage
gcloud run services describe translation-service --region=europe-west1 --format="value(status.conditions)"
```

## 📋 Migration Checklist

- [ ] Build and deploy container image
- [ ] Configure environment variables
- [ ] Set up Eventarc trigger
- [ ] Test with sample documents
- [ ] Monitor performance and costs
- [ ] Update dependent services
- [ ] Decommission old Cloud Function (if applicable)

## 💰 Cost Optimization

### **Resource Management**
- Start with 2GB memory, scale up if needed
- Set concurrency to 1 for memory-intensive operations
- Use min-instances=0 to avoid idle costs
- Set appropriate timeout to avoid unnecessary charges

### **Monitoring Costs**
- Track cost per translation job
- Set up billing alerts
- Monitor resource usage patterns
- Optimize batch sizes for efficiency

## 🔄 API Reference

### **HTTP Endpoints**

#### `POST /`
Main translation endpoint triggered by Eventarc events.

**Request Body:**
```json
{
  "data": {
    "message": {
      "data": "base64-encoded-job-data"
    }
  }
}
```

**Response:**
```json
{
  "status": "completed",
  "final_gcs_path": "gs://bucket/path/to/translated/document.docx"
}
```

### **Eventarc Event Structure**
```json
{
  "data": {
    "message": {
      "data": "eyJqb2JfaWQiOiAidGVzdC1qb2ItMTIzIn0="
    }
  }
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review Cloud Logging for error details
3. Monitor service metrics
4. Contact the development team

---

**Note**: This service is designed for production use with large document translations. Ensure proper resource allocation and monitoring for optimal performance.
