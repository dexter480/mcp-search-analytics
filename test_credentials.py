#!/usr/bin/env python3
"""
Test script to verify Google Analytics and Search Console credentials
"""

import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient

# Load environment variables
load_dotenv()

def test_credentials():
    """Test Google Analytics and Search Console credentials"""
    
    # Get environment variables
    credentials_path = os.environ.get('ANALYTICS_CREDENTIALS_PATH')
    site_url = os.environ.get('GSC_SITE_URL')
    ga4_property_id = os.environ.get('GA4_PROPERTY_ID')
    
    print(f"Credentials path: {credentials_path}")
    print(f"GSC Site URL: {site_url}")
    print(f"GA4 Property ID: {ga4_property_id}")
    print()
    
    if not credentials_path:
        print("[ERROR] ANALYTICS_CREDENTIALS_PATH not set")
        return False
    
    if not os.path.exists(credentials_path):
        print(f"[ERROR] Credentials file not found at {credentials_path}")
        return False
    
    try:
        # Test service account credentials
        print("Testing service account credentials...")
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[
                'https://www.googleapis.com/auth/webmasters.readonly', 
                'https://www.googleapis.com/auth/analytics.readonly'
            ]
        )
        print("✓ Service account credentials loaded successfully")
        
        # Test GSC service
        print("Testing Google Search Console service...")
        gsc_service = build('searchconsole', 'v1', credentials=creds)
        print("✓ Google Search Console service initialized")
        
        # Test GA4 client
        print("Testing Google Analytics 4 client...")
        ga4_client = BetaAnalyticsDataClient(credentials=creds)
        print("✓ Google Analytics 4 client initialized")
        
        print()
        print("[SUCCESS] All credentials and services are working correctly!")
        return True
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

if __name__ == "__main__":
    success = test_credentials()
    if success:
        print("\nYour MCP server should work correctly.")
    else:
        print("\nPlease fix the credential issues before running the MCP server.") 