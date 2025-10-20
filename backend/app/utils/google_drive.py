from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging
from typing import Optional
from app.utils.database import get_supabase_client

logger = logging.getLogger(__name__)


async def get_google_token(user_id: str) -> Optional[str]:
    """Get Google access token for user from database"""
    try:
        supabase = get_supabase_client()

        # First check if we have stored Google tokens in profiles
        response = supabase.table('profiles').select(
            'google_access_token'
        ).eq('id', user_id).execute()

        result = response.data[0] if response.data else None

        if result and result.get('google_access_token'):
            return result['google_access_token']

        # If not stored, the token might be in the session
        # For now, we'll need to pass it from frontend
        return None

    except Exception as e:
        logger.error(f"Error getting Google token: {e}")
        return None


def get_drive_service(access_token: str):
    """Build Google Drive service with access token"""
    credentials = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=credentials)
    return service
