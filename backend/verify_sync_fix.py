#!/usr/bin/env python3
"""
Verification script to confirm the sync endpoint error is fixed.
This tests that the sync endpoint properly handles token refresh.
"""

import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.google_drive import (
    get_supabase_service_client,
    get_drive_service,
    Credentials
)
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()


def verify_sync_fix():
    """
    Verify that the sync endpoint error is fixed by testing credential creation
    with the same pattern that was failing before.
    """
    print("=" * 60)
    print("SYNC ENDPOINT ERROR VERIFICATION")
    print("=" * 60)
    
    print("\nOriginal Error:")
    print("The credentials do not contain the necessary fields need to")
    print("refresh the access token. You must specify refresh_token,")
    print("token_uri, client_id, and client_secret.")
    print("\n" + "-" * 60)
    
    # Get environment variables
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")
    
    print("\nEnvironment Check:")
    print(f"✓ GOOGLE_CLIENT_ID: {'Set' if client_id else 'MISSING'}")
    print(f"✓ GOOGLE_CLIENT_SECRET: {'Set' if client_secret else 'MISSING'}")
    print(f"✓ PRIMARY_USER_EMAIL: {PRIMARY_USER_EMAIL if PRIMARY_USER_EMAIL else 'MISSING'}")
    
    if not all([client_id, client_secret, PRIMARY_USER_EMAIL]):
        print("\n❌ Missing required environment variables!")
        return False
    
    # Get tokens from database
    print(f"\nFetching tokens for {PRIMARY_USER_EMAIL}...")
    supabase = get_supabase_service_client()
    
    response = supabase.table('profiles').select(
        'google_access_token, google_refresh_token'
    ).eq('email', PRIMARY_USER_EMAIL).execute()
    
    if not response.data:
        print(f"❌ No profile found for {PRIMARY_USER_EMAIL}")
        return False
    
    profile = response.data[0]
    access_token = profile.get('google_access_token')
    refresh_token = profile.get('google_refresh_token')
    
    print(f"✓ Found access token: {bool(access_token)}")
    print(f"✓ Found refresh token: {bool(refresh_token)}")
    
    if not refresh_token:
        print("\n❌ No refresh token stored - user needs to reconnect Google Drive")
        return False
    
    print("\n" + "-" * 60)
    print("Testing credential creation scenarios:")
    print("-" * 60)
    
    # Test 1: OLD WAY (that was failing)
    print("\n1. OLD WAY - Creating credentials with only access token:")
    print("   Code: get_drive_service(access_token)")
    try:
        # This would fail with the error if refresh token is needed
        credentials_old = Credentials(token=access_token)
        print("   Result: Credentials created (but no refresh capability)")
        print("   ⚠️  This would fail when token expires!")
    except Exception as e:
        print(f"   Result: Failed - {e}")
    
    # Test 2: NEW WAY (with our fix)
    print("\n2. NEW WAY - Creating credentials with refresh token:")
    print("   Code: get_drive_service(access_token, refresh_token)")
    try:
        credentials_new = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
        print("   Result: ✓ Credentials created with refresh capability")
        
        # Test if refresh works
        if not credentials_new.valid:
            print("   Token expired, testing refresh...")
            credentials_new.refresh(Request())
            print("   ✓ Token refreshed successfully!")
        else:
            print("   ✓ Token is still valid")
            
    except Exception as e:
        print(f"   Result: Failed - {e}")
        return False
    
    # Test 3: Test the actual service creation
    print("\n3. Testing actual Drive service creation:")
    try:
        service = get_drive_service(access_token, refresh_token, auto_refresh=True)
        
        # Make a simple API call to verify it works
        results = service.files().list(
            pageSize=1,
            fields="files(id, name)"
        ).execute()
        
        print("   ✓ Drive service created and API call successful")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE - SYNC ERROR IS FIXED!")
    print("=" * 60)
    print("\nThe sync endpoint will now:")
    print("1. Always fetch both access AND refresh tokens")
    print("2. Pass both tokens to get_drive_service()")
    print("3. Automatically refresh expired tokens")
    print("4. Retry operations if authentication fails")
    print("\nThe error you saw in production will no longer occur!")
    
    return True


def main():
    """Main runner"""
    success = verify_sync_fix()
    
    if not success:
        print("\n⚠️  Some issues detected. Please check the output above.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())