#!/usr/bin/env python3
"""
Migration script to help transition from Cloud Function to Cloud Run.
This script automates the migration process and validates the deployment.
"""

import os
import sys
import json
import subprocess
import time
import requests
from typing import Dict, List, Optional

class CloudRunMigration:
    def __init__(self, project_id: str, region: str = "europe-west1"):
        self.project_id = project_id
        self.region = region
        self.service_name = "translation-service"
        self.bucket_name = "manuskripte-upload-avid-infinity"
        
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met for migration."""
        print("🔍 Checking prerequisites...")
        
        # Check if gcloud is installed and authenticated
        try:
            result = subprocess.run(["gcloud", "auth", "list"], 
                                  capture_output=True, text=True, check=True)
            if "No credentialed accounts" in result.stdout:
                print("❌ No authenticated gcloud accounts found")
                return False
            print("✅ gcloud authentication verified")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ gcloud CLI not found or not working")
            return False
        
        # Check if required APIs are enabled
        apis = [
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "containerregistry.googleapis.com",
            "eventarc.googleapis.com"
        ]
        
        for api in apis:
            try:
                result = subprocess.run([
                    "gcloud", "services", "list", "--enabled", 
                    f"--filter=name:{api}", "--format=value(name)"
                ], capture_output=True, text=True, check=True)
                
                if api not in result.stdout:
                    print(f"⚠️ API {api} not enabled. Enabling...")
                    subprocess.run(["gcloud", "services", "enable", api], check=True)
                    print(f"✅ API {api} enabled")
                else:
                    print(f"✅ API {api} already enabled")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to check/enable API {api}: {e}")
                return False
        
        return True
    
    def build_and_deploy(self) -> bool:
        """Build and deploy the Cloud Run service."""
        print("🏗️ Building and deploying Cloud Run service...")
        
        try:
            # Build the container
            print("📦 Building container image...")
            build_cmd = [
                "gcloud", "builds", "submit",
                "--tag", f"gcr.io/{self.project_id}/{self.service_name}",
                "--project", self.project_id
            ]
            
            result = subprocess.run(build_cmd, check=True, capture_output=True, text=True)
            print("✅ Container built successfully")
            
            # Deploy to Cloud Run
            print("🚀 Deploying to Cloud Run...")
            deploy_cmd = [
                "gcloud", "run", "deploy", self.service_name,
                "--image", f"gcr.io/{self.project_id}/{self.service_name}",
                "--platform", "managed",
                "--region", self.region,
                "--allow-unauthenticated",
                "--memory", "4Gi",
                "--cpu", "2",
                "--timeout", "3600",
                "--max-instances", "10",
                "--min-instances", "0",
                "--concurrency", "1",
                "--set-env-vars", f"GCP_PROJECT={self.project_id}",
                "--project", self.project_id
            ]
            
            result = subprocess.run(deploy_cmd, check=True, capture_output=True, text=True)
            print("✅ Cloud Run service deployed successfully")
            
            # Extract service URL
            for line in result.stdout.split('\n'):
                if 'Service URL:' in line:
                    self.service_url = line.split('Service URL:')[1].strip()
                    print(f"🌐 Service URL: {self.service_url}")
                    break
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Deployment failed: {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            return False
    
    def setup_eventarc_trigger(self) -> bool:
        """Set up Eventarc trigger for Cloud Storage events."""
        print("🔗 Setting up Eventarc trigger...")
        
        try:
            trigger_cmd = [
                "gcloud", "eventarc", "triggers", "create", "translation-trigger",
                "--location", self.region,
                "--destination-run-service", self.service_name,
                "--destination-run-region", self.region,
                "--event-filters", "type=google.cloud.storage.object.v1.finalized",
                "--event-filters", f"bucket={self.bucket_name}",
                "--project", self.project_id
            ]
            
            result = subprocess.run(trigger_cmd, check=True, capture_output=True, text=True)
            print("✅ Eventarc trigger created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create Eventarc trigger: {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            return False
    
    def test_deployment(self) -> bool:
        """Test the deployed service."""
        print("🧪 Testing deployment...")
        
        if not hasattr(self, 'service_url'):
            print("❌ Service URL not available")
            return False
        
        try:
            # Test health check
            response = requests.get(f"{self.service_url}/", timeout=10)
            if response.status_code == 200:
                print("✅ Health check passed")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
            
            # Test translation endpoint with mock event
            mock_event = {
                "data": {
                    "message": {
                        "data": "eyJqb2JfaWQiOiAidGVzdC1qb2ItMTIzIn0="  # base64 encoded {"job_id": "test-job-123"}
                    }
                }
            }
            
            response = requests.post(
                f"{self.service_url}/",
                json=mock_event,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in [200, 400]:  # 400 is expected for missing job
                print("✅ Translation endpoint test passed")
                return True
            else:
                print(f"❌ Translation endpoint test failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def create_service_account(self) -> bool:
        """Create service account with required permissions."""
        print("👤 Creating service account...")
        
        service_account_name = f"{self.service_name}-sa"
        service_account_email = f"{service_account_name}@{self.project_id}.iam.gserviceaccount.com"
        
        try:
            # Create service account
            subprocess.run([
                "gcloud", "iam", "service-accounts", "create", service_account_name,
                "--display-name", "Translation Service Account",
                "--description", "Service account for Cloud Run translation service",
                "--project", self.project_id
            ], check=True)
            
            print(f"✅ Service account created: {service_account_email}")
            
            # Grant required permissions (no OpenAI API key needed with Gemini embeddings)
            permissions = [
                "roles/storage.objectViewer",
                "roles/datastore.user",
                "roles/aiplatform.user",
                "roles/logging.logWriter"
            ]
            
            for permission in permissions:
                subprocess.run([
                    "gcloud", "projects", "add-iam-policy-binding", self.project_id,
                    "--member", f"serviceAccount:{service_account_email}",
                    "--role", permission
                ], check=True)
                print(f"✅ Granted permission: {permission}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create service account: {e}")
            return False
    
    def cleanup_old_resources(self) -> bool:
        """Clean up old Cloud Function resources (optional)."""
        print("🧹 Checking for old Cloud Function resources...")
        
        try:
            # List Cloud Functions
            result = subprocess.run([
                "gcloud", "functions", "list",
                "--filter", "name:translation",
                "--format", "value(name)",
                "--project", self.project_id
            ], capture_output=True, text=True)
            
            if result.stdout.strip():
                print("⚠️ Found old Cloud Function resources:")
                for func_name in result.stdout.strip().split('\n'):
                    print(f"   - {func_name}")
                
                response = input("Do you want to delete these old resources? (y/N): ")
                if response.lower() == 'y':
                    for func_name in result.stdout.strip().split('\n'):
                        if func_name:
                            subprocess.run([
                                "gcloud", "functions", "delete", func_name,
                                "--quiet",
                                "--project", self.project_id
                            ], check=True)
                            print(f"✅ Deleted: {func_name}")
                else:
                    print("ℹ️ Old resources preserved")
            else:
                print("✅ No old Cloud Function resources found")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Could not check for old resources: {e}")
            return True  # Non-critical error
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        print("🚀 Starting Cloud Run migration...")
        print("=" * 60)
        
        steps = [
            ("Checking prerequisites", self.check_prerequisites),
            ("Creating service account", self.create_service_account),
            ("Building and deploying", self.build_and_deploy),
            ("Setting up Eventarc trigger", self.setup_eventarc_trigger),
            ("Testing deployment", self.test_deployment),
            ("Cleaning up old resources", self.cleanup_old_resources)
        ]
        
        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            if not step_func():
                print(f"❌ Migration failed at: {step_name}")
                return False
            print(f"✅ {step_name} completed")
        
        print("\n" + "=" * 60)
        print("🎉 Migration completed successfully!")
        print(f"🌐 Service URL: {getattr(self, 'service_url', 'Not available')}")
        print("📚 Next steps:")
        print("   1. Update your application to use the new Cloud Run service")
        print("   2. Monitor the service performance and costs")
        print("   3. Set up monitoring and alerting")
        print("   4. Test with real translation jobs")
        
        return True

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python migrate-to-cloud-run.py <PROJECT_ID> [REGION]")
        print("Example: python migrate-to-cloud-run.py my-project-id europe-west1")
        sys.exit(1)
    
    project_id = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "europe-west1"
    
    print(f"🔄 Migrating to Cloud Run for project: {project_id}")
    print(f"📍 Region: {region}")
    
    migration = CloudRunMigration(project_id, region)
    
    if migration.run_migration():
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
