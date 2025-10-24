from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
import logging
import os
import mimetypes
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher
from supabase import create_client, Client

logger = logging.getLogger(__name__)


def get_supabase_service_client() -> Client:
    """Get Supabase client with service role for bypassing RLS"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    # Try service role key first, fall back to anon key
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_SERVICE_KEY:
        # Use anon key as fallback
        SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_google_token(user_id: str) -> Optional[str]:
    """Get Google access token for user from database"""
    try:
        supabase = get_supabase_service_client()

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


def get_drive_service(access_token: str, refresh_token: Optional[str] = None):
    """
    Build Google Drive service with credentials that support auto-refresh.

    Args:
        access_token: Google OAuth access token
        refresh_token: Google OAuth refresh token (optional, but required for auto-refresh)

    Returns:
        Google Drive service instance
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    # If we have refresh token and client credentials, create full OAuth credentials
    if refresh_token and client_id and client_secret:
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        # Fallback: credentials without refresh (will fail when token expires)
        logger.warning("Creating credentials without refresh token - uploads will fail when token expires")
        credentials = Credentials(token=access_token)

    service = build('drive', 'v3', credentials=credentials)
    return service


def find_best_matching_folder(service, parent_folder_id: str, project_name: str) -> Optional[Dict[str, str]]:
    """
    Find the best matching folder within the parent folder based on project name similarity.
    
    Args:
        service: Google Drive API service instance
        parent_folder_id: The ID of the parent folder to search in
        project_name: The project name to match against
    
    Returns:
        Dict with folder 'id' and 'name' if found, None otherwise
    """
    try:
        # List all folders in the parent folder
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(
            q=query,
            fields='files(id, name)',
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        if not folders:
            logger.warning(f"No folders found in parent folder {parent_folder_id}")
            return None
        
        # Find best match using string similarity
        best_match = None
        best_score = 0.0
        
        # Normalize project name for comparison
        normalized_project = project_name.lower().strip()
        
        for folder in folders:
            folder_name = folder['name']
            normalized_folder = folder_name.lower().strip()
            
            # Calculate similarity score
            score = SequenceMatcher(None, normalized_project, normalized_folder).ratio()
            
            # Also check if one contains the other (partial match)
            if normalized_project in normalized_folder or normalized_folder in normalized_project:
                score = max(score, 0.8)  # Boost score for partial matches
            
            if score > best_score:
                best_score = score
                best_match = folder
        
        # Only return if we have a reasonable match (threshold of 0.5)
        if best_score >= 0.5:
            logger.info(f"Found matching folder '{best_match['name']}' for project '{project_name}' (score: {best_score:.2f})")
            return best_match
        else:
            logger.warning(f"No good match found for project '{project_name}' (best score: {best_score:.2f})")
            return None
            
    except Exception as e:
        logger.error(f"Error finding matching folder: {e}")
        return None


def upload_attachment_to_drive(
    file_data: bytes,
    original_filename: str,
    company_name: str,
    trade: str,
    project_name: str,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    drive_root_folder_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload an attachment to Google Drive with proper naming and folder structure.

    Args:
        file_data: The raw file bytes to upload
        original_filename: The original filename (for extension extraction)
        company_name: The company name extracted from the document
        trade: The trade/work type extracted from the document
        project_name: The project name the document belongs to
        access_token: Google OAuth access token. If not provided, will fetch from database
        refresh_token: Google OAuth refresh token. If not provided, will fetch from database
        drive_root_folder_id: Root folder ID in Google Drive. If not provided, will get from database

    Returns:
        Dict containing the Google Drive file ID and web link
    """
    try:
        # Get tokens and Drive folder from database if not provided
        if not access_token or not drive_root_folder_id:
            PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")
            if not PRIMARY_USER_EMAIL:
                raise ValueError("PRIMARY_USER_EMAIL not configured in environment")

            supabase = get_supabase_service_client()

            # Get user's profile with tokens and Drive folder
            response = supabase.table('profiles').select(
                'google_access_token, google_refresh_token, drive_root_folder_id'
            ).eq('email', PRIMARY_USER_EMAIL).execute()

            if not response.data:
                raise RuntimeError(f"No profile found for {PRIMARY_USER_EMAIL}")

            profile = response.data[0]

            if not access_token:
                access_token = profile.get('google_access_token')
            if not refresh_token:
                refresh_token = profile.get('google_refresh_token')
            if not drive_root_folder_id:
                drive_root_folder_id = profile.get('drive_root_folder_id')

            if not access_token:
                raise RuntimeError(f"No Google access token found for {PRIMARY_USER_EMAIL}. Please sign in to the dashboard to connect Google Drive.")

            if not drive_root_folder_id:
                raise RuntimeError(f"No Drive root folder configured for {PRIMARY_USER_EMAIL}. Please configure it in the dashboard.")

        logger.info(f"Using Google Drive root folder: {drive_root_folder_id}")

        # Get Drive service with refresh capability
        service = get_drive_service(access_token, refresh_token)
        
        # Extract file extension from original filename
        _, extension = os.path.splitext(original_filename)
        if not extension or extension.lower() not in ['.pdf', '.docx', '.doc']:
            extension = '.pdf'  # Default to PDF if no valid extension
        
        # Clean company name and trade for filename
        clean_company = (company_name or "unknown").replace('/', '-').replace('\\', '-').replace(':', '-').strip()
        clean_trade = (trade or "unknown").replace('/', '-').replace('\\', '-').replace(':', '-').strip()
        
        # Create filename: {trade}_{company_name}.pdf (or appropriate extension)
        new_filename = f"{clean_trade}_{clean_company}{extension}"
        
        # Find best matching project folder within the root folder
        folder_id = None
        matched_folder = None
        
        if project_name and drive_root_folder_id:
            matched_folder = find_best_matching_folder(service, drive_root_folder_id, project_name)
            if matched_folder:
                folder_id = matched_folder['id']
                logger.info(f"Using matched folder '{matched_folder['name']}' for project: {project_name}")
            else:
                # If no match found, create or use "Uncertain Bids" folder
                logger.warning(f"No matching folder found for project '{project_name}', checking for Uncertain Bids folder")
                
                # Check if "Uncertain Bids" folder exists in root folder
                query = f"'{drive_root_folder_id}' in parents and name='Uncertain Bids' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = service.files().list(
                    q=query,
                    fields='files(id, name)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                uncertain_folders = results.get('files', [])
                
                if uncertain_folders:
                    # Use existing "Uncertain Bids" folder
                    folder_id = uncertain_folders[0]['id']
                    matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
                    logger.info("Using existing 'Uncertain Bids' folder")
                else:
                    # Create "Uncertain Bids" folder in root folder
                    folder_metadata = {
                        'name': 'Uncertain Bids',
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [drive_root_folder_id]
                    }
                    folder = service.files().create(
                        body=folder_metadata,
                        fields='id, name',
                        supportsAllDrives=True
                    ).execute()
                    folder_id = folder.get('id')
                    matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
                    logger.info("Created new 'Uncertain Bids' folder")
        else:
            # No project name provided, use "Uncertain Bids" folder
            logger.info("No project name provided, using Uncertain Bids folder")
            
            # Check if "Uncertain Bids" folder exists
            query = f"'{drive_root_folder_id}' in parents and name='Uncertain Bids' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = service.files().list(
                q=query,
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            uncertain_folders = results.get('files', [])
            
            if uncertain_folders:
                folder_id = uncertain_folders[0]['id']
                matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
            else:
                # Create "Uncertain Bids" folder
                folder_metadata = {
                    'name': 'Uncertain Bids',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [drive_root_folder_id]
                }
                folder = service.files().create(
                    body=folder_metadata,
                    fields='id, name',
                    supportsAllDrives=True
                ).execute()
                folder_id = folder.get('id')
                matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
        
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
            fields='id, name, webViewLink, webContentLink',
            supportsAllDrives=True
        ).execute()
        
        logger.info(f"Successfully uploaded file to Google Drive: {new_filename} in folder: {matched_folder['name'] if matched_folder else 'Unknown'}")
        
        return {
            'success': True,
            'file_id': file.get('id'),
            'file_name': file.get('name'),
            'web_view_link': file.get('webViewLink'),
            'web_content_link': file.get('webContentLink'),
            'folder_id': folder_id,
            'folder_name': matched_folder['name'] if matched_folder else 'root',
            'project_name': project_name
        }
        
    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {e}")
        return {
            'success': False,
            'error': str(e)
        }
