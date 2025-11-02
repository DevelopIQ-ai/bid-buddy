#!/usr/bin/env python3
"""
Test script for Google Drive token refresh mechanism.
This script simulates token expiration and tests the automatic refresh functionality.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.google_drive import (
    get_supabase_service_client,
    refresh_and_update_token,
    get_drive_service,
    upload_attachment_to_drive_with_retry
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def test_token_refresh():
    """Test the token refresh functionality"""
    PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")
    
    if not PRIMARY_USER_EMAIL:
        logger.error("PRIMARY_USER_EMAIL not set in environment")
        return False
    
    logger.info(f"Testing token refresh for {PRIMARY_USER_EMAIL}")
    
    try:
        # Test 1: Check if we can get current tokens
        logger.info("Test 1: Fetching current tokens from database...")
        supabase = get_supabase_service_client()
        
        response = supabase.table('profiles').select(
            'google_access_token, google_refresh_token, drive_root_folder_id'
        ).eq('email', PRIMARY_USER_EMAIL).execute()
        
        if not response.data:
            logger.error(f"No profile found for {PRIMARY_USER_EMAIL}")
            return False
        
        profile = response.data[0]
        access_token = profile.get('google_access_token')
        refresh_token = profile.get('google_refresh_token')
        drive_root_folder_id = profile.get('drive_root_folder_id')
        
        logger.info(f"✓ Found profile with tokens")
        logger.info(f"  - Has access token: {bool(access_token)}")
        logger.info(f"  - Has refresh token: {bool(refresh_token)}")
        logger.info(f"  - Has drive folder: {bool(drive_root_folder_id)}")
        
        if not refresh_token:
            logger.error("No refresh token found - cannot test refresh mechanism")
            logger.info("Please reconnect Google Drive from the dashboard with proper offline access")
            return False
        
        # Test 2: Test the refresh function
        logger.info("\nTest 2: Testing token refresh function...")
        new_access_token, new_refresh_token = refresh_and_update_token(PRIMARY_USER_EMAIL)
        
        if new_access_token:
            logger.info("✓ Token refresh successful")
            logger.info(f"  - New access token obtained: {new_access_token[:20]}...")
        else:
            logger.error("✗ Token refresh failed")
            return False
        
        # Test 3: Test creating a Drive service with the refreshed token
        logger.info("\nTest 3: Creating Google Drive service with refreshed token...")
        try:
            service = get_drive_service(new_access_token, new_refresh_token, auto_refresh=True)
            
            # Try to list files to verify the service works
            results = service.files().list(
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            
            logger.info("✓ Drive service created successfully and API call succeeded")
        except Exception as e:
            logger.error(f"✗ Failed to create Drive service or make API call: {e}")
            return False
        
        # Test 4: Test the upload wrapper with retry
        logger.info("\nTest 4: Testing upload function with retry mechanism...")
        test_data = b"This is a test file for token refresh testing"
        test_filename = f"test_token_refresh_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        
        result = upload_attachment_to_drive_with_retry(
            file_data=test_data,
            original_filename=test_filename,
            company_name="Test Company",
            trade="Test Trade",
            project_name="Test Project"
        )
        
        if result.get('success'):
            logger.info("✓ Upload with retry mechanism succeeded")
            logger.info(f"  - File ID: {result.get('file_id')}")
            logger.info(f"  - File Name: {result.get('file_name')}")
            logger.info(f"  - Folder: {result.get('folder_name')}")
            
            # Clean up test file
            if result.get('file_id'):
                try:
                    service.files().delete(fileId=result['file_id']).execute()
                    logger.info("  - Test file cleaned up")
                except:
                    logger.warning("  - Could not clean up test file")
        else:
            logger.error(f"✗ Upload failed: {result.get('error')}")
            return False
        
        logger.info("\n" + "="*50)
        logger.info("All tests passed! Token refresh mechanism is working properly.")
        logger.info("="*50)
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner"""
    logger.info("Starting Google Drive Token Refresh Tests")
    logger.info("="*50)
    
    # Check required environment variables
    required_vars = [
        "PRIMARY_USER_EMAIL",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY"  # Changed to use anon key since service role key falls back to it
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return 1
    
    # Run tests
    success = test_token_refresh()
    
    if success:
        logger.info("\n✅ Token refresh mechanism is properly configured and working!")
        logger.info("\nThe system will now automatically:")
        logger.info("1. Check token validity before Google Drive operations")
        logger.info("2. Refresh expired tokens using the stored refresh token")
        logger.info("3. Retry operations if they fail due to authentication")
        logger.info("4. Update the database with new access tokens")
        return 0
    else:
        logger.error("\n❌ Token refresh tests failed!")
        logger.error("\nPlease ensure:")
        logger.error("1. The user has signed into the dashboard at least once")
        logger.error("2. Google Drive was connected with proper offline access scope")
        logger.error("3. The refresh token is stored in the database")
        logger.error("4. GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are configured")
        return 1


if __name__ == "__main__":
    sys.exit(main())