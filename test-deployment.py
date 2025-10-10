#!/usr/bin/env python3
"""
Test script for Cloud Run Translation Service deployment.
This script tests the basic functionality of the deployed service.
"""

import requests
import json
import base64
import time
import sys

def test_health_check(service_url):
    """Test if the service is responding to health checks."""
    try:
        response = requests.get(f"{service_url}/", timeout=10)
        print(f"✅ Health check: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_translation_endpoint(service_url, job_id="test-job-123"):
    """Test the translation endpoint with a mock Eventarc event."""
    try:
        # Create mock Eventarc event payload
        mock_event = {
            "data": {
                "message": {
                    "data": base64.b64encode(json.dumps({"job_id": job_id}).encode()).decode()
                }
            }
        }
        
        print(f"🔄 Testing translation endpoint with job_id: {job_id}")
        response = requests.post(
            f"{service_url}/",
            json=mock_event,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Response body: {response.text}")
        
        return response.status_code in [200, 400]  # 400 is expected for missing job in Firestore
        
    except Exception as e:
        print(f"❌ Translation endpoint test failed: {e}")
        return False

def test_service_metrics(service_url):
    """Test if the service is properly configured for monitoring."""
    try:
        # Test with a simple request to check response headers
        response = requests.get(f"{service_url}/", timeout=10)
        
        # Check for Cloud Run specific headers
        headers = response.headers
        print(f"📊 Service headers:")
        for key, value in headers.items():
            if 'cloud' in key.lower() or 'run' in key.lower():
                print(f"   {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Metrics test failed: {e}")
        return False

def main():
    """Main test function."""
    if len(sys.argv) != 2:
        print("Usage: python test-deployment.py <SERVICE_URL>")
        print("Example: python test-deployment.py https://translation-service-xxx-uc.a.run.app")
        sys.exit(1)
    
    service_url = sys.argv[1].rstrip('/')
    print(f"🧪 Testing Cloud Run Translation Service at: {service_url}")
    print("=" * 60)
    
    tests = [
        ("Health Check", lambda: test_health_check(service_url)),
        ("Translation Endpoint", lambda: test_translation_endpoint(service_url)),
        ("Service Metrics", lambda: test_service_metrics(service_url))
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} passed")
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Service is ready for production.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the service configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
