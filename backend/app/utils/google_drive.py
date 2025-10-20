from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
import logging
import os
import mimetypes
from typing import Optional, Dict, Any
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


def upload_attachment_to_drive(
    file_data: bytes,
    original_filename: str,
    company_name: str,
    trade: str,
    project_name: str,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload an attachment to Google Drive with proper naming and folder structure.
    
    Args:
        file_data: The raw file bytes to upload
        original_filename: The original filename (for extension extraction)
        company_name: The company name extracted from the document
        trade: The trade/work type extracted from the document
        project_name: The project name the document belongs to
        access_token: Google OAuth access token. If not provided, will get from first user
    
    Returns:
        Dict containing the Google Drive file ID and web link
    """
    try:
        # Get access token if not provided (assume single user for now)
        if not access_token:
            supabase = get_supabase_client()
            # Get the first user's Google token
            response = supabase.table('profiles').select('google_access_token').limit(1).execute()
            if response.data and response.data[0].get('google_access_token'):
                access_token = response.data[0]['google_access_token']
            else:
                raise Exception("No Google access token found for any user")
        
        # Get Drive service
        service = get_drive_service(access_token)
        
        # Extract file extension from original filename
        _, extension = os.path.splitext(original_filename)
        if not extension:
            extension = '.pdf'  # Default to PDF if no extension
        
        # Clean company name and trade for filename
        clean_company = (company_name or "unknown").replace('/', '-').replace('\\', '-').strip()
        clean_trade = (trade or "unknown").replace('/', '-').replace('\\', '-').strip()
        
        # Create filename: {trade}_{company}.{extension}
        new_filename = f"{clean_trade}_{clean_company}{extension}"
        
        # Find or create project folder
        folder_id = None
        if project_name:
            # Search for existing folder with the project name
            query = f"name='{project_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                # Use existing folder
                folder_id = folders[0]['id']
                logger.info(f"Using existing folder for project: {project_name}")
            else:
                # Create new folder for the project
                folder_metadata = {
                    'name': project_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                folder_id = folder.get('id')
                logger.info(f"Created new folder for project: {project_name}")
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # Prepare file metadata
        file_metadata = {
            'name': new_filename
        }
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Upload file
        media = MediaInMemoryUpload(
            file_data,
            mimetype=mime_type,
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink'
        ).execute()
        
        logger.info(f"Successfully uploaded file to Google Drive: {new_filename}")
        
        return {
            'success': True,
            'file_id': file.get('id'),
            'file_name': file.get('name'),
            'web_view_link': file.get('webViewLink'),
            'web_content_link': file.get('webContentLink'),
            'folder_id': folder_id,
            'project_name': project_name
        }
        
    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {e}")
        return {
            'success': False,
            'error': str(e)
        }
